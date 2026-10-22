import unittest
import json
from backend.app import create_app

class TestCafeNestAPI(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_menu_listing(self):
        res = self.client.get('/api/menu')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['count'], 0)
        self.assertIn('name', data['data'][0])
        self.assertIn('price', data['data'][0])

    def test_02_categories_listing(self):
        res = self.client.get('/api/menu/categories')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(len(data['data']), 0)

    def test_03_customer_login_success(self):
        res = self.client.post('/api/auth/login', json={
            'email': 'aarav@gmail.com',
            'password': 'customer123',
            'login_type': 'customer'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['name'], 'Aarav Sharma')

    def test_04_customer_login_invalid(self):
        res = self.client.post('/api/auth/login', json={
            'email': 'aarav@gmail.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data['success'])

    def test_05_admin_login_success(self):
        res = self.client.post('/api/auth/login', json={
            'email': 'admin@cafenest.com',
            'password': 'admin123',
            'login_type': 'staff'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['role'], 'Admin')

    def test_06_order_placement_and_validation(self):
        # 1. Reject empty cart
        res = self.client.post('/api/orders', json={'items': []})
        self.assertEqual(res.status_code, 400)

        # 2. Reject non-positive quantity
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': -1}],
            'order_type': 'Takeaway'
        })
        self.assertEqual(res.status_code, 400)

        # 3. Valid order placement
        res = self.client.post('/api/orders', json={
            'items': [
                {'menu_id': 1, 'quantity': 1}, # Velvet Cortado: 190.00
                {'menu_id': 10, 'quantity': 2} # Croissant: 180.00 * 2 = 360.00
            ],
            'order_type': 'Takeaway',
            'special_instructions': 'Extra hot and crispy'
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        order_info = data['data']
        self.assertEqual(order_info['subtotal'], 550.00)
        self.assertEqual(order_info['tax_amount'], 27.50) # 5% GST
        self.assertEqual(order_info['total_amount'], 577.50)
        order_id = order_info['order_id']

        # 4. Process simulated payment
        pay_res = self.client.post('/api/payments/demo', json={
            'order_id': order_id,
            'method': 'Simulated_UPI'
        })
        self.assertEqual(pay_res.status_code, 200)
        pay_data = pay_res.get_json()
        self.assertTrue(pay_data['success'])
        self.assertTrue(pay_data['data']['is_simulated'])

    def test_07_tables_listing(self):
        res = self.client.get('/api/tables')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 12)

if __name__ == '__main__':
    unittest.main()
