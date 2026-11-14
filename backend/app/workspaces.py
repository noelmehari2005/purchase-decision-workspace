"""Local workspace contracts and immutable, server-evaluated review creation."""
from datetime import datetime, timezone
import re
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from .import_models import ImportEvidence
from .schemas import Contract, EvaluationInput, LaptopInput, PreferencesInput
from .domain import Requirements, evaluate

Text = Annotated[str, Field(max_length=300)]
AmountText = Annotated[str, Field(max_length=20)]


def amount(value: str, label: str, optional=False):
    if not value.strip() and optional:
        return None
    if not re.fullmatch(r'\d+(\.\d{1,2})?', value.strip()):
        raise ValueError(f'{label}: enter a nonnegative amount with at most two decimal places.')
    whole, _, fraction = value.strip().partition('.')
    return int(whole) * 100 + int(fraction.ljust(2, '0') or '0')


def measure(value: str):
    if not value.strip():
        return None
    if not re.fullmatch(r'\d+', value) or not 0 < int(value) <= 10_000_000:
        raise ValueError('Measurements must be positive whole numbers or unknown.')
    return int(value)


class LaptopDraft(Contract):
    id: Annotated[str, Field(min_length=1, max_length=80)]
    current: bool
    name: Annotated[str, Field(max_length=200)]
    configuration: Text
    cpu: Text
    os: Text
    ram: AmountText
    storage: AmountText
    compatible: Literal['yes', 'no', 'unknown']
    costMode: Literal['components', 'provisional']
    price: AmountText
    tax: AmountText
    shipping: AmountText
    other: AmountText
    provisional: AmountText
    weight: AmountText
    battery: AmountText
    batteryContext: Text
    source: Annotated[str, Field(max_length=2000)]
    notes: Annotated[str, Field(max_length=3000)]
    display: Text = ''
    maxRam: AmountText = ''
    batteryWh: AmountText = ''
    evidence: ImportEvidence | None = None

    @field_validator('source')
    @classmethod
    def safe_source(cls, value):
        from urllib.parse import urlsplit
        if value:
            try:
                parsed = urlsplit(value)
                valid = parsed.scheme in ('http', 'https') and bool(parsed.hostname)
            except ValueError:
                valid = False
            if not valid:
                raise ValueError('Source links must be complete http or https URLs.')
        return value

    def evaluation_input(self):
        return LaptopInput(id=self.id, current=self.current, name=self.name,
            configuration=self.configuration, confirmed=True, ram_gb=measure(self.ram),
            storage_gb=measure(self.storage), compatible=self.compatible,
            weight_g=measure(self.weight), battery_minutes=measure(self.battery),
            battery_context=self.batteryContext, cost={
                'mode': self.costMode, 'item_cents': amount(self.price, 'Item price', True),
                'tax_cents': amount(self.tax, 'Tax', True), 'shipping_cents': amount(self.shipping, 'Shipping', True),
                'other_cents': amount(self.other, 'Other costs'),
                'provisional_cents': amount(self.provisional, 'Provisional total', self.costMode != 'provisional')})


class CandidateRecord(Contract):
    draft: LaptopDraft
    confirmed: LaptopDraft | None
    revision: Annotated[int, Field(strict=True, ge=0, le=1_000_000)]

    @model_validator(mode='after')
    def consistent_confirmation(self):
        if self.confirmed:
            if self.revision < 1 or (self.confirmed.id, self.confirmed.current) != (self.draft.id, self.draft.current):
                raise ValueError('Confirmed candidate identity and revision must match the draft.')
            self.confirmed.evaluation_input()
        elif self.revision != 0:
            raise ValueError('Unconfirmed candidates have revision zero.')
        return self


class RequirementForm(Contract):
    ram: AmountText
    storage: AmountText
    ceiling: AmountText
    noLimit: bool
    compatibility: bool


class Task(Contract):
    name: Text
    selected: bool
    timing: Literal['current', 'upcoming']
    experience: Literal['adequate', 'struggles', 'cannot', 'unknown']


class PlanForm(Contract):
    savings: AmountText
    contribution: AmountText
    firstDate: Annotated[str, Field(max_length=10)]
    targetDate: Annotated[str, Field(max_length=10)]
    essential: bool
    useBudget: bool
    income: AmountText
    housing: AmountText
    food: AmountText
    transportation: AmountText
    other: AmountText
    goals: AmountText
    buffer: AmountText
    useScenario: bool
    category: Literal['housing', 'food', 'transportation', 'other']
    reduction: AmountText
    allocation: AmountText


class WorkspaceState(Contract):
    schemaVersion: Literal[1] = 1
    title: Annotated[str, Field(min_length=1, max_length=120)]
    timezone: Annotated[str, Field(max_length=80)]
    tasks: Annotated[list[Task], Field(max_length=30)]
    customNeeds: Annotated[str, Field(max_length=3000)]
    requirements: RequirementForm
    preferences: PreferencesInput
    records: Annotated[list[CandidateRecord], Field(min_length=1, max_length=20)]
    plan: PlanForm
    outcome: Annotated[str, Field(max_length=100)]
    reason: Annotated[str, Field(max_length=4000)]

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError('Enter a workspace title.')
        return value.strip()

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Choose a valid IANA timezone.')
        return value

    @model_validator(mode='after')
    def record_identity(self):
        if not self.records[0].draft.current or sum(r.draft.current for r in self.records) != 1:
            raise ValueError('Keep exactly one current-laptop baseline as the first record.')
        if len({r.draft.id for r in self.records}) != len(self.records):
            raise ValueError('Candidate identifiers must be unique.')
        choices = {'Investigate and save', 'Keep my current laptop', 'Undecided'}
        choices.update(r.draft.id for r in self.records if r.confirmed and not r.draft.current)
        if self.outcome not in choices:
            raise ValueError('The selected decision must refer to a confirmed replacement or an available direction.')
        return self

    def evaluation_input(self):
        p, r = self.plan, self.requirements
        if p.useScenario and not p.useBudget:
            raise ValueError('Enable the budget before adding a spending scenario.')
        return EvaluationInput(candidates=[c.confirmed.evaluation_input() for c in self.records if c.confirmed],
            requirements={'min_ram_gb': measure(r.ram), 'min_storage_gb': measure(r.storage),
                          'max_cost_cents': None if r.noLimit else amount(r.ceiling, 'Price ceiling', True),
                          'require_compatibility': r.compatibility}, preferences=self.preferences,
            plan={'savings_cents': amount(p.savings, 'Savings'), 'contribution_cents': amount(p.contribution, 'Contribution'),
                  'first_date': p.firstDate, 'target_date': p.targetDate or None, 'essential_deadline': p.essential,
                  'budget': {'income_cents': amount(p.income, 'Income', True),
                             'expenses': {k: amount(getattr(p, k), k, True) for k in ('housing','food','transportation','other')},
                             'goals_cents': amount(p.goals, 'Other goals', True), 'buffer_cents': amount(p.buffer, 'Buffer', True)} if p.useBudget else None,
                  'scenario': {'category': p.category, 'reduction_cents': amount(p.reduction, 'Reduction'),
                               'allocation_cents': amount(p.allocation, 'Allocation')} if p.useScenario else None})


class CreateWorkspace(Contract):
    request_id: UUID
    state: WorkspaceState


class UpdateWorkspace(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    state: WorkspaceState


class DeleteWorkspace(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    confirmation: Literal['DELETE']


class CreateSnapshot(Contract):
    request_id: UUID
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


class StorageError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def now():
    return datetime.now(timezone.utc).isoformat()


def ensure_candidate_revisions(previous, state):
    old = {c['draft']['id']: c for c in previous['records']}
    for record in state['records']:
        prior = old.get(record['draft']['id'])
        if not prior:
            continue
        if prior['draft']['current'] != record['draft']['current']:
            raise ValueError('A candidate cannot change its baseline identity.')
        if record['revision'] < prior['revision']:
            raise ValueError('Candidate revisions cannot move backward.')
        old_confirmed = LaptopDraft.model_validate(prior['confirmed']).model_dump(mode='json') if prior['confirmed'] else None
        new_confirmed = LaptopDraft.model_validate(record['confirmed']).model_dump(mode='json') if record['confirmed'] else None
        if new_confirmed != old_confirmed and record['revision'] <= prior['revision']:
            raise ValueError('Confirm a new candidate revision before replacing reviewed values.')


def build_snapshot(workspace, request_id):
    state = WorkspaceState.model_validate(workspace['state'])
    payload = state.evaluation_input()
    if not payload.candidates:
        raise ValueError('Confirm at least one laptop before saving a review.')
    result = evaluate([c.to_domain() for c in payload.candidates], Requirements(**payload.requirements.model_dump()),
                      payload.plan.to_domain(), payload.preferences.model_dump())
    # One already-read, immutable revision supplies both state and authoritative result.
    return {'id': str(request_id), 'decision_id': workspace['id'], 'decision_revision': workspace['revision'],
            'schema_version': 1, 'created_at': now(), 'state': state.model_dump(mode='json'),
            'evaluation_input': payload.model_dump(mode='json'), 'evaluation': result}
