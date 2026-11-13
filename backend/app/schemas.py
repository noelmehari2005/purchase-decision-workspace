"""Validated HTTP contracts; domain functions do not depend on these models."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import domain

Cents = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000_000)]
Measurement = Annotated[int, Field(strict=True, gt=0, le=10_000_000)]
Importance = Literal['high', 'medium', 'low', 'ignored']
ShortText = Annotated[str, Field(max_length=200)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class CostInput(Contract):
    mode: Literal['components', 'provisional'] = 'components'
    item_cents: Cents | None = None
    tax_cents: Cents | None = None
    shipping_cents: Cents | None = None
    other_cents: Cents = 0
    provisional_cents: Cents | None = None

    @model_validator(mode='after')
    def provisional_needs_total(self):
        if self.mode == 'provisional' and self.provisional_cents is None:
            raise ValueError('Enter a provisional total or choose component costs.')
        return self


class LaptopInput(Contract):
    id: Annotated[str, Field(min_length=1, max_length=80)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    configuration: Annotated[str, Field(min_length=1, max_length=300)]
    confirmed: Literal[True]
    current: bool = False
    ram_gb: Measurement | None = None
    storage_gb: Measurement | None = None
    compatible: Literal['yes', 'no', 'unknown'] = 'unknown'
    cost: CostInput = Field(default_factory=CostInput)
    weight_g: Measurement | None = None
    battery_minutes: Measurement | None = None
    battery_context: Annotated[str, Field(max_length=500)] = ''

    @field_validator('name', 'configuration')
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Enter a nonblank product name and configuration.')
        return value.strip()

    def to_domain(self) -> domain.Laptop:
        return domain.Laptop(**self.model_dump(exclude={'confirmed', 'cost'}),
                             cost=domain.Cost(**self.cost.model_dump()))


class RequirementsInput(Contract):
    min_ram_gb: Measurement | None = None
    min_storage_gb: Measurement | None = None
    max_cost_cents: Cents | None = None
    require_compatibility: bool = False


class BudgetInput(Contract):
    income_cents: Cents | None = None
    expenses: Annotated[dict[Annotated[str, Field(min_length=1, max_length=80)], Cents | None], Field(min_length=1, max_length=20)]
    goals_cents: Cents | None = None
    buffer_cents: Cents | None = None


class ScenarioInput(Contract):
    category: Annotated[str, Field(min_length=1, max_length=80)]
    reduction_cents: Cents
    allocation_cents: Cents


class PlanInput(Contract):
    savings_cents: Cents
    contribution_cents: Cents
    first_date: date
    target_date: date | None = None
    essential_deadline: bool = False
    budget: BudgetInput | None = None
    scenario: ScenarioInput | None = None

    def to_domain(self) -> domain.Plan:
        return domain.Plan(**self.model_dump(exclude={'budget', 'scenario'}),
                           budget=domain.Budget(**self.budget.model_dump()) if self.budget else None,
                           scenario=domain.Scenario(**self.scenario.model_dump()) if self.scenario else None)


class PreferencesInput(Contract):
    performance: Importance = 'high'
    portability: Importance = 'medium'
    battery: Importance = 'medium'
    repairability: Importance = 'low'
    cost: Importance = 'ignored'


class EvaluationInput(Contract):
    candidates: Annotated[list[LaptopInput], Field(max_length=20)]
    requirements: RequirementsInput
    plan: PlanInput
    preferences: PreferencesInput = Field(default_factory=PreferencesInput)

    @model_validator(mode='after')
    def unique_candidates(self):
        if len({item.id for item in self.candidates}) != len(self.candidates):
            raise ValueError('Candidate identifiers must be unique.')
        if sum(item.current for item in self.candidates) > 1:
            raise ValueError('Only one laptop can be the current-device baseline.')
        return self


class PurchasePlanOutput(Contract):
    status: Literal['unknown', 'funded', 'unreachable', 'date_limit', 'planned']
    remaining_cents: int | None
    contributions: int | None
    reachable_date: str | None
    available_contributions: int | None
    required_monthly_cents: int | None
    last_contribution_cents: int | None
    meets_target: bool | None


class CheckOutput(Contract):
    label: str
    status: Literal['met', 'failed', 'unknown']
    reason: str


class CandidateOutput(Contract):
    id: str
    group: Literal['met', 'failed', 'unknown', 'unset']
    checks: list[CheckOutput]
    cost_cents: int | None
    provisional: bool
    base_plan: PurchasePlanOutput
    scenario_plan: PurchasePlanOutput | None
    suggested_contribution_cents: int | None
    advantages: list[str]


class EvaluationOutput(Contract):
    versions: dict[str, str]
    budget_capacity_cents: int | None
    scenario_contribution_cents: int | None
    scenario_capacity_cents: int | None
    warnings: list[str]
    candidates: list[CandidateOutput]
