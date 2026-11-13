"""Hand-calculated examples and invariants from the accepted design."""

from copy import deepcopy
from datetime import date
import unittest

from backend.app.domain import (
    Budget, Cost, Laptop, Plan, Requirements, Scenario,
    assess, contribution_date, evaluate, purchase_plan,
)


class CalendarTests(unittest.TestCase):
    def test_original_anchor_survives_february(self):
        anchor = date(2027, 1, 31)
        self.assertEqual(contribution_date(anchor, 1), date(2027, 2, 28))
        self.assertEqual(contribution_date(anchor, 2), date(2027, 3, 31))

    def test_leap_year(self):
        self.assertEqual(contribution_date(date(2028, 1, 31), 1), date(2028, 2, 29))

    def test_target_is_inclusive(self):
        result = purchase_plan(80_000, 30_000, 15_000, date(2027, 1, 31), date(2027, 3, 31))
        self.assertEqual(result['available_contributions'], 3)
        self.assertEqual(result['required_monthly_cents'], 16_667)
        self.assertFalse(result['meets_target'])
        self.assertEqual(result['reachable_date'], '2027-04-30')

    def test_target_before_first_contribution(self):
        result = purchase_plan(100, 0, 50, date(2027, 2, 1), date(2027, 1, 31))
        self.assertEqual(result['available_contributions'], 0)
        self.assertIsNone(result['required_monthly_cents'])
        self.assertFalse(result['meets_target'])

    def test_before_anchor_day_does_not_count_month(self):
        result = purchase_plan(100, 0, 50, date(2027, 1, 31), date(2027, 3, 30))
        self.assertEqual(result['available_contributions'], 2)


class SavingsTests(unittest.TestCase):
    def test_alex_examples(self):
        for cost, rate, count in [(80_000, 15_000, 4), (110_000, 15_000, 6),
                                  (80_000, 19_000, 3), (110_000, 19_000, 5)]:
            with self.subTest(cost=cost, rate=rate):
                result = purchase_plan(cost, 30_000, rate, date(2027, 1, 31))
                self.assertEqual(result['contributions'], count)

    def test_cents_and_last_payment(self):
        result = purchase_plan(501, 0, 167, date(2027, 1, 1), date(2027, 3, 1))
        self.assertEqual(result['contributions'], 3)
        self.assertEqual(result['last_contribution_cents'], 167)
        self.assertTrue(result['meets_target'])
        result = purchase_plan(500, 0, 167, date(2027, 1, 1))
        self.assertEqual(result['last_contribution_cents'], 166)

    def test_zero_contribution_is_unreachable(self):
        result = purchase_plan(100, 0, 0, date(2027, 1, 1))
        self.assertEqual(result['status'], 'unreachable')
        self.assertIsNone(result['reachable_date'])

    def test_already_funded_even_without_future_contributions(self):
        result = purchase_plan(100, 200, 0, date(2027, 1, 1), date(2026, 1, 1))
        self.assertEqual(result['status'], 'funded')
        self.assertEqual(result['required_monthly_cents'], 0)

    def test_missing_cost_is_unknown_not_free(self):
        self.assertEqual(purchase_plan(None, 100, 100, date(2027, 1, 1))['status'], 'unknown')

    def test_extremely_distant_plan_does_not_overflow(self):
        result = purchase_plan(1_000_000_000, 0, 1, date(2027, 1, 1))
        self.assertEqual(result['status'], 'date_limit')
        self.assertIsNone(result['reachable_date'])

    def test_more_contribution_never_delays_purchase(self):
        for gap in [1, 99, 100, 10_001, 50_000]:
            a = purchase_plan(gap, 0, 100, date(2027, 1, 1))
            b = purchase_plan(gap, 0, 101, date(2027, 1, 1))
            self.assertLessEqual(b['contributions'], a['contributions'])


class CostAndEligibilityTests(unittest.TestCase):
    def laptop(self, **kwargs):
        return Laptop(id='a', name='A', configuration='Model A', **kwargs)

    def test_missing_component_makes_total_unknown(self):
        self.assertEqual(Cost(item_cents=80_000).selected(), (None, False))

    def test_provisional_total_overrides_not_adds(self):
        cost = Cost(mode='provisional', item_cents=80_000, tax_cents=1000,
                    shipping_cents=0, provisional_cents=90_000)
        self.assertEqual(cost.selected(), (90_000, True))

    def test_failure_dominates_unknown(self):
        result = assess(self.laptop(ram_gb=8), Requirements(min_ram_gb=16, min_storage_gb=512))
        self.assertEqual(result['group'], 'failed')
        self.assertEqual([c['status'] for c in result['checks']], ['failed', 'unknown'])

    def test_unknown_is_not_failure(self):
        self.assertEqual(assess(self.laptop(), Requirements(min_ram_gb=16))['group'], 'unknown')

    def test_all_checks_met(self):
        self.assertEqual(assess(self.laptop(ram_gb=16), Requirements(min_ram_gb=16))['group'], 'met')

    def test_empty_requirements_are_not_suitability(self):
        self.assertEqual(assess(self.laptop(), Requirements())['group'], 'unset')

    def test_ceiling_independent_from_compatibility(self):
        laptop = self.laptop(compatible='no', cost=Cost(item_cents=110_000, tax_cents=0, shipping_cents=0))
        self.assertEqual(assess(laptop, Requirements(max_cost_cents=90_000))['group'], 'failed')
        self.assertEqual(assess(laptop, Requirements())['group'], 'unset')
        self.assertEqual(assess(laptop, Requirements(require_compatibility=True))['group'], 'failed')

    def test_provisional_under_ceiling_is_not_confirmed_pass(self):
        laptop = self.laptop(cost=Cost(mode='provisional', provisional_cents=80_000))
        self.assertEqual(assess(laptop, Requirements(max_cost_cents=90_000))['group'], 'unknown')


class EvaluationTests(unittest.TestCase):
    def base(self, **kwargs):
        return Plan(savings_cents=30_000, contribution_cents=15_000,
                    first_date=date(2027, 1, 31), target_date=date(2027, 3, 31), **kwargs)

    def test_budget_and_scenario_do_not_mutate_base(self):
        budget = Budget(income_cents=160_000, expenses={'housing': 70_000, 'food': 25_000,
                        'transportation': 18_000, 'other': 12_000}, goals_cents=15_000, buffer_cents=5000)
        original = deepcopy(budget)
        plan = self.base(budget=budget, scenario=Scenario('transportation', 4000, 3000))
        result = evaluate([Laptop('a', 'A', 'A', cost=Cost(item_cents=80_000, tax_cents=0, shipping_cents=0))], Requirements(), plan)
        self.assertEqual(budget, original)
        self.assertEqual(result['budget_capacity_cents'], 15_000)
        self.assertEqual(result['candidates'][0]['suggested_contribution_cents'], 15_000)
        self.assertEqual(result['scenario_contribution_cents'], 18_000)
        self.assertEqual(result['candidates'][0]['base_plan']['contributions'], 4)
        self.assertEqual(result['candidates'][0]['scenario_plan']['contributions'], 3)

    def test_negative_balance_is_preserved(self):
        budget = Budget(income_cents=100, expenses={'food': 200}, goals_cents=0, buffer_cents=0)
        result = evaluate([Laptop('a', 'A', 'A', cost=Cost(item_cents=1000, tax_cents=0, shipping_cents=0))], Requirements(), self.base(budget=budget))
        self.assertEqual(result['budget_capacity_cents'], -100)

    def test_incomplete_budget_produces_no_suggestion(self):
        budget = Budget(income_cents=100, expenses={'food': None}, goals_cents=0, buffer_cents=0)
        self.assertIsNone(evaluate([], Requirements(), self.base(budget=budget))['budget_capacity_cents'])

    def test_invalid_reduction_and_allocation(self):
        budget = Budget(income_cents=1000, expenses={'food': 100}, goals_cents=0, buffer_cents=0)
        for reduction, allocation in [(101, 50), (100, 101)]:
            with self.subTest(reduction=reduction, allocation=allocation), self.assertRaises(ValueError):
                evaluate([], Requirements(), self.base(budget=budget, scenario=Scenario('food', reduction, allocation)))

    def test_no_deadline_means_no_automatic_suggestion(self):
        plan = Plan(0, 100, date(2027, 1, 1), budget=Budget(1000, {'food': 100}, 0, 0))
        result = evaluate([Laptop('a', 'A', 'A', cost=Cost(item_cents=1000, tax_cents=0, shipping_cents=0))], Requirements(), plan)
        self.assertIsNone(result['candidates'][0]['suggested_contribution_cents'])

    def test_unknown_battery_context_is_not_ranked(self):
        laptops = [Laptop('a', 'A', 'A', ram_gb=16, battery_minutes=600),
                   Laptop('b', 'B', 'B', ram_gb=16, battery_minutes=300)]
        result = evaluate(laptops, Requirements(min_ram_gb=16), self.base(), {'battery': 'high'})
        self.assertTrue(all(not row['advantages'] for row in result['candidates']))


if __name__ == '__main__':
    unittest.main()
