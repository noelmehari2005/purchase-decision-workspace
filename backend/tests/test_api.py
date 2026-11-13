from copy import deepcopy
import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = {
            'candidates': [{'id': 'a', 'name': 'Laptop A', 'configuration': '16/512',
                            'confirmed': True, 'ram_gb': 16, 'storage_gb': 512,
                            'cost': {'item_cents': 80_000, 'tax_cents': 0, 'shipping_cents': 0}}],
            'requirements': {'min_ram_gb': 16, 'max_cost_cents': 90_000},
            'plan': {'savings_cents': 30_000, 'contribution_cents': 15_000,
                     'first_date': '2027-01-31', 'target_date': '2027-03-31'},
        }

    def test_health(self):
        self.assertEqual(self.client.get('/api/v1/health').json()['mode'], 'local-stateless')

    def test_confirmed_evaluation(self):
        response = self.client.post('/api/v1/evaluations', json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()['candidates'][0]
        self.assertEqual(row['group'], 'met')
        self.assertEqual(row['base_plan']['reachable_date'], '2027-04-30')

    def test_money_rejects_coercion(self):
        for value in [-1, 1.5, '15000', True]:
            payload = deepcopy(self.payload)
            payload['plan']['contribution_cents'] = value
            with self.subTest(value=value):
                self.assertEqual(self.client.post('/api/v1/evaluations', json=payload).status_code, 422)

    def test_confirmation_gate(self):
        self.payload['candidates'][0]['confirmed'] = False
        self.assertEqual(self.client.post('/api/v1/evaluations', json=self.payload).status_code, 422)

    def test_unknown_fields_and_duplicate_ids_rejected(self):
        payload = deepcopy(self.payload)
        payload['candidates'].append(payload['candidates'][0])
        self.assertEqual(self.client.post('/api/v1/evaluations', json=payload).status_code, 422)
        self.payload['owner_id'] = 'untrusted'
        self.assertEqual(self.client.post('/api/v1/evaluations', json=self.payload).status_code, 422)

    def test_incomplete_candidate_is_allowed(self):
        self.payload['candidates'][0].pop('ram_gb')
        response = self.client.post('/api/v1/evaluations', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['candidates'][0]['group'], 'unknown')

    def test_invalid_scenario_is_useful_422(self):
        self.payload['plan'].update(budget={'income_cents': 100, 'expenses': {'food': 50},
                                          'goals_cents': 0, 'buffer_cents': 0},
                                    scenario={'category': 'food', 'reduction_cents': 51, 'allocation_cents': 20})
        response = self.client.post('/api/v1/evaluations', json=self.payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'invalid_plan')

    def test_invalid_provisional_cost(self):
        self.payload['candidates'][0]['cost'] = {'mode': 'provisional'}
        response = self.client.post('/api/v1/evaluations', json=self.payload)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('input', response.json())

    def test_storage_opt_in_and_no_import_endpoints(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'PDW_LOCAL_STORAGE': '0'}):
            self.assertEqual(self.client.get('/api/v1/decisions').status_code, 503)


if __name__ == '__main__':
    unittest.main()
