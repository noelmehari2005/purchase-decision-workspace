export type Importance = 'high' | 'medium' | 'low' | 'ignored'
export type Group = 'met' | 'unknown' | 'failed' | 'unset'
export interface LaptopDraft {
  id: string; current: boolean; name: string; configuration: string; cpu: string; os: string;
  ram: string; storage: string; compatible: 'yes' | 'no' | 'unknown';
  costMode: 'components' | 'provisional'; price: string; tax: string; shipping: string;
  other: string; provisional: string; weight: string; battery: string; batteryContext: string;
  source: string; notes: string;
}
export interface CandidateRecord { draft: LaptopDraft; confirmed: LaptopDraft | null; revision: number }
export interface RequirementForm { ram: string; storage: string; ceiling: string; noLimit: boolean; compatibility: boolean }
export interface PlanForm {
  savings: string; contribution: string; firstDate: string; targetDate: string; essential: boolean;
  useBudget: boolean; income: string; housing: string; food: string; transportation: string;
  other: string; goals: string; buffer: string; useScenario: boolean;
  category: string; reduction: string; allocation: string;
}
export interface PurchasePlan {
  status: 'unknown' | 'funded' | 'unreachable' | 'date_limit' | 'planned';
  remaining_cents: number | null; contributions: number | null; reachable_date: string | null;
  available_contributions: number | null; required_monthly_cents: number | null;
  last_contribution_cents: number | null; meets_target: boolean | null;
}
export interface CandidateResult {
  id: string; group: Group; checks: {label: string; status: string; reason: string}[];
  cost_cents: number | null; provisional: boolean; base_plan: PurchasePlan;
  scenario_plan: PurchasePlan | null; suggested_contribution_cents: number | null; advantages: string[];
}
export interface Evaluation {
  versions: Record<string, string>; budget_capacity_cents: number | null;
  scenario_contribution_cents: number | null; scenario_capacity_cents: number | null;
  warnings: string[]; candidates: CandidateResult[];
}
export const money = (cents: number | null) => cents === null ? 'Unknown' :
  new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(cents / 100)

export function cents(text: string, label: string, optional = false): number | null {
  if (!text.trim() && optional) return null
  if (!/^\d+(\.\d{1,2})?$/.test(text.trim())) throw new Error(`${label}: enter a nonnegative dollar amount with at most two decimal places.`)
  const [whole, fraction = ''] = text.trim().split('.')
  const value = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  if (!Number.isSafeInteger(value) || value > 1_000_000_000_000) throw new Error(`${label}: amount is too large.`)
  return value
}
export function measurement(text: string, label: string): number | null {
  if (!text.trim()) return null
  if (!/^\d+$/.test(text) || Number(text) <= 0 || Number(text) > 10_000_000)
    throw new Error(`${label}: enter a positive whole number or leave it unknown.`)
  return Number(text)
}
export function candidateInput(d: LaptopDraft) {
  if (!d.name.trim() || !d.configuration.trim()) throw new Error('Enter a product name and identify the exact configuration. Specifications may remain unknown.')
  if (d.source.trim()) {
    let url: URL
    try { url = new URL(d.source) } catch { throw new Error('Source link: enter a complete http or https URL, or leave it blank.') }
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Source link: only http or https is supported.')
  }
  const cost = {
    mode: d.costMode, item_cents: cents(d.price, 'Item price', true),
    tax_cents: cents(d.tax, 'Tax', true), shipping_cents: cents(d.shipping, 'Shipping', true),
    other_cents: cents(d.other, 'Other purchase costs'),
    provisional_cents: cents(d.provisional, 'Provisional total', d.costMode !== 'provisional'),
  }
  return { id: d.id, name: d.name.trim(), configuration: d.configuration.trim(), current: d.current,
    confirmed: true as const, ram_gb: measurement(d.ram, 'RAM'), storage_gb: measurement(d.storage, 'Storage'),
    compatible: d.compatible, cost, weight_g: measurement(d.weight, 'Weight'),
    battery_minutes: measurement(d.battery, 'Battery runtime'), battery_context: d.batteryContext }
}
export function evaluationInput(records: CandidateRecord[], r: RequirementForm, p: PlanForm, preferences: Record<string, Importance>) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(p.firstDate)) throw new Error('Choose the first monthly contribution date.')
  if (p.useScenario && !p.useBudget) throw new Error('Enable the budget before creating a spending-change scenario.')
  const expenseKeys = ['housing', 'food', 'transportation', 'other'] as const
  return {
    candidates: records.filter(record => record.confirmed).map(record => candidateInput(record.confirmed!)),
    requirements: { min_ram_gb: measurement(r.ram, 'Minimum RAM'), min_storage_gb: measurement(r.storage, 'Minimum storage'),
      max_cost_cents: r.noLimit ? null : cents(r.ceiling, 'Maximum price', true), require_compatibility: r.compatibility },
    preferences,
    plan: {
      savings_cents: cents(p.savings, 'Purchase savings'), contribution_cents: cents(p.contribution, 'Monthly contribution'),
      first_date: p.firstDate, target_date: p.targetDate || null, essential_deadline: p.essential,
      budget: p.useBudget ? {income_cents: cents(p.income, 'Income', true),
        expenses: Object.fromEntries(expenseKeys.map(key => [key, cents(p[key], key, true)])),
        goals_cents: cents(p.goals, 'Other goals', true), buffer_cents: cents(p.buffer, 'Unallocated buffer', true)} : null,
      scenario: p.useScenario ? {category: p.category, reduction_cents: cents(p.reduction, 'Reduction'),
        allocation_cents: cents(p.allocation, 'Purchase allocation')} : null,
    },
  }
}

export function newLaptop(id: string, current = false): LaptopDraft {
  return { id, current, name: current ? 'My current laptop' : '', configuration: '', cpu: '', os: '', ram: '', storage: '',
    compatible: 'unknown', costMode: 'components', price: current ? '0' : '', tax: current ? '0' : '',
    shipping: current ? '0' : '', other: '0', provisional: '', weight: '', battery: '', batteryContext: '', source: '', notes: '' }
}
export function initialRecords(): CandidateRecord[] {
  const current = {...newLaptop('current', true), configuration: 'Alex’s existing configuration', ram: '8', storage: '256',
    notes: 'Basic programming works. Running my editor, browser, backend, and database together feels slow.'}
  const a = {...newLaptop('example-a'), name: 'Candidate A — fictional', configuration: 'Example A · 16 GB / 512 GB',
    ram: '16', storage: '512', price: '800', tax: '0', shipping: '0', weight: '1400'}
  const b = {...newLaptop('example-b'), name: 'Candidate B — fictional', configuration: 'Example B · 32 GB / 1 TB',
    ram: '32', storage: '1000', price: '1100', tax: '0', shipping: '0', weight: '1800'}
  return [current, a, b].map(draft => ({draft, confirmed: null, revision: 0}))
}

export function planLabel(plan: PurchasePlan): string {
  if (plan.status === 'unknown') return 'Cost incomplete — timeline unknown'
  if (plan.status === 'funded') return 'Already funded under these assumptions'
  if (plan.status === 'unreachable') return 'Not reached at $0 per month'
  if (plan.status === 'date_limit') return 'Purchase date is beyond the supported calendar range'
  return `${plan.contributions} monthly contributions · ${plan.reachable_date}`
}

export interface WorkspaceState {
  schemaVersion: 1; title: string; timezone: string;
  tasks: {name: string; selected: boolean; timing: string; experience: string}[];
  customNeeds: string; requirements: RequirementForm; preferences: Record<string, Importance>;
  records: CandidateRecord[]; plan: PlanForm; outcome: string; reason: string;
}
export interface SavedWorkspace {id: string; revision: number; created_at: string; updated_at: string; state: WorkspaceState}
export interface SavedReview {
  id: string; decision_id: string; decision_revision: number; created_at: string;
  state: WorkspaceState; evaluation: Evaluation;
}
