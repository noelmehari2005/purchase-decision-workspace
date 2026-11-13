"""Deterministic rules. No HTTP, database, clock, or provider dependencies.

Money is integer USD cents. Calendar dates are supplied in the user's timezone.
Evidence quality is not inferred from RAM, CPU names, or an overall score.
"""

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date

MODEL_VERSIONS = {'calculation': '1.0.0', 'assessment': '1.0.0', 'guidance': '1.0.0'}


def nonnegative(value: int | None, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer.')


@dataclass(frozen=True)
class Cost:
    mode: str = 'components'
    item_cents: int | None = None
    tax_cents: int | None = None
    shipping_cents: int | None = None
    other_cents: int = 0
    provisional_cents: int | None = None

    def __post_init__(self):
        for key in ('item_cents', 'tax_cents', 'shipping_cents', 'provisional_cents'):
            nonnegative(getattr(self, key), key, optional=True)
        nonnegative(self.other_cents, 'other_cents')
        if self.mode not in ('components', 'provisional'):
            raise ValueError('Select components or provisional cost mode.')
        if self.mode == 'provisional' and self.provisional_cents is None:
            raise ValueError('Enter a provisional total or choose component costs.')

    def selected(self) -> tuple[int | None, bool]:
        if self.mode == 'provisional':
            return self.provisional_cents, True
        parts = (self.item_cents, self.tax_cents, self.shipping_cents)
        if any(part is None for part in parts):
            return None, False
        return sum(part for part in parts if part is not None) + self.other_cents, False


@dataclass(frozen=True)
class Laptop:
    id: str
    name: str
    configuration: str
    ram_gb: int | None = None
    storage_gb: int | None = None
    compatible: str = 'unknown'
    cost: Cost = field(default_factory=Cost)
    weight_g: int | None = None
    battery_minutes: int | None = None
    battery_context: str = ''
    current: bool = False


@dataclass(frozen=True)
class Requirements:
    min_ram_gb: int | None = None
    min_storage_gb: int | None = None
    max_cost_cents: int | None = None
    require_compatibility: bool = False


@dataclass(frozen=True)
class Budget:
    income_cents: int | None
    expenses: dict[str, int | None]
    goals_cents: int | None
    buffer_cents: int | None

    def capacity(self) -> int | None:
        values = [self.income_cents, self.goals_cents, self.buffer_cents, *self.expenses.values()]
        for value in values:
            nonnegative(value, 'Budget amounts', optional=True)
        if any(value is None for value in values) or not self.expenses:
            return None
        return self.income_cents - self.goals_cents - self.buffer_cents - sum(self.expenses.values())


@dataclass(frozen=True)
class Scenario:
    category: str
    reduction_cents: int
    allocation_cents: int


@dataclass(frozen=True)
class Plan:
    savings_cents: int
    contribution_cents: int
    first_date: date
    target_date: date | None = None
    budget: Budget | None = None
    scenario: Scenario | None = None
    essential_deadline: bool = False


def contribution_date(anchor: date, offset: int) -> date:
    """Recalculate from the ORIGINAL anchor, so February doesn't shift March."""
    nonnegative(offset, 'Month offset')
    index = anchor.year * 12 + anchor.month - 1 + offset
    year, month_index = divmod(index, 12)
    if year > 9999:
        raise ValueError('Purchase date exceeds the supported calendar range.')
    month = month_index + 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def available_contributions(anchor: date, target: date) -> int:
    if target < anchor:
        return 0
    months = (target.year - anchor.year) * 12 + target.month - anchor.month
    return months + (1 if contribution_date(anchor, months) <= target else 0)


def purchase_plan(cost: int | None, savings: int, contribution: int,
                  first_date: date, target: date | None = None) -> dict:
    for value, name in ((cost, 'Cost'), (savings, 'Savings'), (contribution, 'Contribution')):
        nonnegative(value, name, optional=name == 'Cost')
    available = available_contributions(first_date, target) if target else None
    result = {'status': 'unknown', 'remaining_cents': None, 'contributions': None,
              'reachable_date': None, 'available_contributions': available,
              'required_monthly_cents': None, 'last_contribution_cents': None,
              'meets_target': None}
    if cost is None:
        return result
    gap = max(0, cost - savings)
    result['remaining_cents'] = gap
    if available is not None:
        result['required_monthly_cents'] = (gap + available - 1) // available if available else (0 if gap == 0 else None)
        result['meets_target'] = contribution * available >= gap
    if gap == 0:
        return {**result, 'status': 'funded', 'contributions': 0, 'last_contribution_cents': 0}
    if contribution == 0:
        return {**result, 'status': 'unreachable'}
    count = (gap + contribution - 1) // contribution
    result.update(contributions=count, last_contribution_cents=gap - contribution * (count - 1))
    try:
        reachable = contribution_date(first_date, count - 1)
    except ValueError:
        return {**result, 'status': 'date_limit'}
    return {**result, 'status': 'planned', 'reachable_date': reachable.isoformat()}


def assess(laptop: Laptop, requirements: Requirements) -> dict:
    checks = []
    for label, value, minimum in (
        ('Installed RAM (GB)', laptop.ram_gb, requirements.min_ram_gb),
        ('Installed storage (GB)', laptop.storage_gb, requirements.min_storage_gb),
    ):
        if minimum is not None:
            status = 'unknown' if value is None else 'met' if value >= minimum else 'failed'
            checks.append({'label': label, 'status': status,
                           'reason': f'Minimum {minimum}; ' + ('value unknown.' if value is None else f'entered value {value}.')})
    cost, provisional = laptop.cost.selected()
    if requirements.max_cost_cents is not None:
        status = 'unknown' if cost is None or provisional else 'met' if cost <= requirements.max_cost_cents else 'failed'
        reason = 'Total cost unknown.' if cost is None else ('Provisional total: price eligibility remains unconfirmed.' if provisional else 'Compared with your selected ceiling.')
        checks.append({'label': 'Maximum total purchase price', 'status': status, 'reason': reason})
    if requirements.require_compatibility:
        status = {'yes': 'met', 'no': 'failed', 'unknown': 'unknown'}[laptop.compatible]
        checks.append({'label': 'Required-tool compatibility', 'status': status,
                       'reason': 'Based on your entered compatibility evidence; no automatic tool diagnosis.'})
    statuses = {check['status'] for check in checks}
    group = 'unset' if not checks else 'failed' if 'failed' in statuses else 'unknown' if 'unknown' in statuses else 'met'
    return {'group': group, 'checks': checks}


def preference_advantages(laptops: list[Laptop], rows: list[dict], preferences: dict[str, str]) -> None:
    """Only describe observed extrema when every eligible peer has evidence.

    Importance is displayed, not converted into an invented combined score.
    Baselines are separate from replacement preference comparisons.
    """
    eligible = [(laptop, row) for laptop, row in zip(laptops, rows)
                if row['group'] == 'met' and not laptop.current]
    if len(eligible) < 2:
        return
    for preference, attribute, lower, description in (
        ('portability', 'weight_g', True, 'Lowest entered weight'),
        ('battery', 'battery_minutes', False, 'Longest entered battery runtime under matching conditions'),
        ('cost', '', True, 'Lowest complete entered purchase cost'),
    ):
        if preferences.get(preference, 'ignored') == 'ignored':
            continue
        if preference == 'battery':
            contexts = {laptop.battery_context.strip() for laptop, _ in eligible}
            if len(contexts) != 1 or not next(iter(contexts)):
                continue
        values = [(laptop.cost.selected()[0] if not laptop.cost.selected()[1] else None)
                  if preference == 'cost' else getattr(laptop, attribute) for laptop, _ in eligible]
        if any(value is None for value in values) or len(set(values)) < 2:
            continue
        best = min(values) if lower else max(values)
        for (_, row), value in zip(eligible, values):
            if value == best:
                row['advantages'].append(f'{description} among these confirmed eligible replacements ({preferences[preference]} priority).')


def evaluate(laptops: list[Laptop], requirements: Requirements, plan: Plan,
             preferences: dict[str, str] | None = None) -> dict:
    nonnegative(plan.savings_cents, 'Savings')
    nonnegative(plan.contribution_cents, 'Contribution')
    capacity = plan.budget.capacity() if plan.budget else None
    scenario_rate = None
    scenario_capacity = None
    if plan.scenario:
        scenario = plan.scenario
        nonnegative(scenario.reduction_cents, 'Reduction')
        nonnegative(scenario.allocation_cents, 'Purchase allocation')
        expense = plan.budget.expenses.get(scenario.category) if plan.budget else None
        if expense is None:
            raise ValueError('A scenario needs a known expense in the selected budget category.')
        if not 0 <= scenario.allocation_cents <= scenario.reduction_cents <= expense:
            raise ValueError('Purchase allocation must not exceed the reduction, and reduction must not exceed the category expense.')
        scenario_rate = plan.contribution_cents + scenario.allocation_cents
        scenario_capacity = capacity + scenario.reduction_cents if capacity is not None else None
    warnings = []
    if plan.budget and capacity is None:
        warnings.append('Budget is incomplete; no contribution suggestion is available.')
    if capacity is not None and plan.contribution_cents > capacity:
        warnings.append('Your contribution exceeds the amount remaining after entered commitments and buffer.')
    if capacity is not None and capacity < 0:
        warnings.append('Your entered budget has a shortfall. It has not been replaced with zero.')
    if scenario_capacity is not None and scenario_rate > scenario_capacity:
        warnings.append('The scenario contribution exceeds the scenario budget capacity.')
    rows = []
    for laptop in laptops:
        cost, provisional = laptop.cost.selected()
        base = purchase_plan(cost, plan.savings_cents, plan.contribution_cents, plan.first_date, plan.target_date)
        alternative = purchase_plan(cost, plan.savings_cents, scenario_rate, plan.first_date, plan.target_date) if scenario_rate is not None else None
        required = base['required_monthly_cents']
        suggested = min(required, max(0, capacity)) if required is not None and capacity is not None else None
        rows.append({'id': laptop.id, **assess(laptop, requirements), 'cost_cents': cost,
                     'provisional': provisional, 'base_plan': base, 'scenario_plan': alternative,
                     'suggested_contribution_cents': suggested, 'advantages': []})
    preference_advantages(laptops, rows, preferences or {})
    return {'versions': MODEL_VERSIONS.copy(), 'budget_capacity_cents': capacity,
            'scenario_contribution_cents': scenario_rate, 'scenario_capacity_cents': scenario_capacity,
            'warnings': warnings, 'candidates': rows}
