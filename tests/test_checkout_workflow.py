import unittest
import json
import pymysql
from backend.app import create_app
from backend.config.db_config import get_db_connection

class TestCheckoutAndOrderPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        # Ensure test table 5 is Available before each test
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE cafe_tables SET status = 'Available' WHERE table_id = 5;")
            cur.execute("UPDATE cafe_tables SET status = 'Occupied' WHERE table_id = 2;")
            # Ensure menu item 1 is Available and item 14 is temporarily set for test
            cur.execute("UPDATE menu SET is_available = TRUE WHERE menu_id IN (1, 2, 3);")
        conn.commit()
        conn.close()

    def test_01_empty_cart_rejection(self):
        """Empty cart must be rejected with HTTP 400 and clear error message."""
        res = self.client.post('/api/orders', json={
            'items': [],
            'order_type': 'Takeaway'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn("empty", data['message'].lower())

    def test_02_invalid_quantities(self):
        """Non-positive or non-integer quantities must be rejected."""
        # Negative quantity
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': -3}],
            'order_type': 'Takeaway'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("positive", res.get_json()['message'].lower())

        # Zero quantity
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 0}],
            'order_type': 'Takeaway'
        })
        self.assertEqual(res.status_code, 400)

        # Non-integer float quantity
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1.5}],
            'order_type': 'Takeaway'
        })
        self.assertEqual(res.status_code, 400)

    def test_03_unavailable_items_rejection(self):
        """Items marked unavailable in SQL must be rejected with an informative message."""
        # Mark menu_id 3 as unavailable
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE menu SET is_available = FALSE WHERE menu_id = 3;")
        conn.commit()
        conn.close()

        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 3, 'quantity': 1}],
            'order_type': 'Takeaway'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertTrue('unavailable' in data['message'].lower() or 'sold out' in data['message'].lower())

        # Restore
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE menu SET is_available = TRUE WHERE menu_id = 3;")
        conn.commit()
        conn.close()

    def test_04_invalid_table_selections(self):
        """Dine-In with non-existent or already occupied table must be rejected."""
        # Non-existent table ID
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Dine-In',
            'table_id': 99999
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("exist", res.get_json()['message'].lower())

        # Occupied table (Table 2 is Occupied)
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Dine-In',
            'table_id': 2
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("occupied", res.get_json()['message'].lower())

    def test_05_successful_checkout_and_sql_verification(self):
        """Valid checkout must recalculate totals from SQL, create orders, order_details, payments, and update table."""
        # Velvet Cortado is ₹190.00, Artisan Flat White is ₹210.00
        # 2x Cortado (380.00) + 1x Flat White (210.00) = Subtotal ₹590.00
        # 5% GST = ₹29.50. Total = ₹619.50
        idemp_key = f"TEST-SUCCESS-{random_key()}"
        res = self.client.post('/api/orders', json={
            'items': [
                {'menu_id': 1, 'quantity': 2},
                {'menu_id': 2, 'quantity': 1}
            ],
            'order_type': 'Dine-In',
            'table_id': 5,
            'customer_name': 'Meera Joshi',
            'customer_phone': '+91 9988776655',
            'customer_email': 'meera@gmail.com',
            'payment_method': 'Simulated_UPI',
            'idempotency_key': idemp_key,
            'special_instructions': 'Extra hot milk in Flat White'
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        order = data['data']
        order_id = order['order_id']
        order_ref = order['order_reference']

        # Verify backend recalculated totals correctly
        self.assertEqual(order['subtotal'], 590.00)
        self.assertEqual(order['tax_amount'], 29.50)
        self.assertEqual(order['total_amount'], 619.50)
        self.assertEqual(order['status'], 'Confirmed')

        # Directly verify records in SQL database using pymysql
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 1. Check orders table
            cur.execute("SELECT * FROM orders WHERE order_id = %s;", (order_id,))
            sql_order = cur.fetchone()
            self.assertIsNotNone(sql_order)
            self.assertEqual(sql_order['order_reference'], order_ref)
            self.assertEqual(sql_order['customer_name'], 'Meera Joshi')
            self.assertEqual(sql_order['customer_phone'], '+91 9988776655')
            self.assertEqual(float(sql_order['subtotal']), 590.00)
            self.assertEqual(float(sql_order['tax_amount']), 29.50)
            self.assertEqual(float(sql_order['total_amount']), 619.50)
            self.assertEqual(sql_order['status'], 'Confirmed')
            self.assertEqual(sql_order['idempotency_key'], idemp_key)

            # 2. Check order_details table
            cur.execute("SELECT * FROM order_details WHERE order_id = %s ORDER BY menu_id;", (order_id,))
            details = cur.fetchall()
            self.assertEqual(len(details), 2)
            self.assertEqual(details[0]['menu_id'], 1)
            self.assertEqual(details[0]['quantity'], 2)
            self.assertEqual(float(details[0]['unit_price']), 190.00)
            self.assertEqual(float(details[0]['subtotal']), 380.00)

            self.assertEqual(details[1]['menu_id'], 2)
            self.assertEqual(details[1]['quantity'], 1)
            self.assertEqual(float(details[1]['unit_price']), 210.00)
            self.assertEqual(float(details[1]['subtotal']), 210.00)

            # 3. Check cafe_tables status updated to 'Occupied'
            cur.execute("SELECT status FROM cafe_tables WHERE table_id = 5;")
            tbl = cur.fetchone()
            self.assertEqual(tbl['status'], 'Occupied')

            # 4. Check payments table
            cur.execute("SELECT * FROM payments WHERE order_id = %s;", (order_id,))
            sql_payment = cur.fetchone()
            self.assertIsNotNone(sql_payment)
            self.assertEqual(sql_payment['method'], 'Simulated_UPI')
            self.assertEqual(sql_payment['status'], 'Completed')
            self.assertEqual(float(sql_payment['amount']), 619.50)
            self.assertTrue(sql_payment['is_simulated'])
        conn.close()

    def test_06_duplicate_submission_prevention(self):
        """Submitting with the same idempotency key must not create duplicate order records in SQL."""
        idemp_key = f"TEST-DUP-{random_key()}"
        payload = {
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Takeaway',
            'customer_name': 'Rohan Shah',
            'payment_method': 'Cash',
            'idempotency_key': idemp_key
        }

        # First submission
        res1 = self.client.post('/api/orders', json=payload)
        self.assertEqual(res1.status_code, 201)
        data1 = res1.get_json()['data']
        initial_order_id = data1['order_id']

        # Second duplicate submission
        res2 = self.client.post('/api/orders', json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertTrue(data2.get('is_duplicate'))
        self.assertEqual(data2['data']['order_id'], initial_order_id)

        # Check in SQL: Exactly one order row exists with this idempotency_key
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE idempotency_key = %s;", (idemp_key,))
            count = cur.fetchone()['cnt']
            self.assertEqual(count, 1)
        conn.close()

    def test_07_client_supplied_totals_are_ignored(self):
        """Tampered client-supplied subtotals and totals must be ignored and recomputed by backend."""
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}], # Velvet Cortado: ₹190.00
            'order_type': 'Takeaway',
            'subtotal': 1.00,      # Tampered client total
            'tax_amount': 0.05,    # Tampered client tax
            'total_amount': 1.05   # Tampered client grand total
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()['data']
        # Backend must have calculated real values: 190.00 + 9.50 = 199.50
        self.assertEqual(data['subtotal'], 190.00)
        self.assertEqual(data['tax_amount'], 9.50)
        self.assertEqual(data['total_amount'], 199.50)

def random_key():
    import string, random
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

if __name__ == '__main__':
    unittest.main()
