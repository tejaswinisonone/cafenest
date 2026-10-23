import unittest
import json
import random
import pymysql
from backend.app import create_app
from backend.config.db_config import get_db_connection

class TestOrderManagementTrackingAndPayments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        # Clean up / reset test tables if needed
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE cafe_tables SET status = 'Available' WHERE table_id = 7;")
            cur.execute("UPDATE menu SET is_available = TRUE WHERE menu_id IN (1, 2, 10);")
        conn.commit()
        conn.close()

    def login_customer(self, email="aarav@gmail.com", password="customer123"):
        return self.client.post('/api/auth/login', json={
            'email': email,
            'password': password,
            'login_type': 'customer'
        })

    def login_staff(self, email="admin@cafenest.com", password="admin123"):
        return self.client.post('/api/auth/login', json={
            'email': email,
            'password': password,
            'login_type': 'staff'
        })

    def test_01_and_02_create_order_and_verify_server_calculated_totals(self):
        """Points 1 & 2: Creating an order with valid items and verifying trusted server calculations."""
        # Velvet Cortado (190.00) x 2 = 380.00
        # Artisanal Croissant (180.00) x 1 = 180.00
        # Subtotal: 560.00, GST (5%): 28.00, Total: 588.00
        res = self.client.post('/api/orders', json={
            'items': [
                {'menu_id': 1, 'quantity': 2},
                {'menu_id': 10, 'quantity': 1}
            ],
            'order_type': 'Takeaway',
            'customer_name': 'Test Patron',
            'customer_phone': '+91 9123456789',
            'payment_method': 'Simulated_UPI'
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()['data']
        self.assertEqual(data['subtotal'], 560.00)
        self.assertEqual(data['tax_amount'], 28.00)
        self.assertEqual(data['total_amount'], 588.00)
        self.assertEqual(data['cafe_name'], 'CaféNest Artisan Roastery')
        self.assertEqual(data['status'], 'Confirmed')

        # Verify in MySQL
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE order_id = %s;", (data['order_id'],))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(float(row['total_amount']), 588.00)
            self.assertEqual(row['cafe_name'], 'CaféNest Artisan Roastery')

            # Verify line items have snapshot item_name
            cur.execute("SELECT item_name, quantity, unit_price FROM order_details WHERE order_id = %s;", (data['order_id'],))
            items = cur.fetchall()
            self.assertEqual(len(items), 2)
            self.assertTrue(all(it['item_name'] for it in items))
        conn.close()

    def test_03_customer_order_history_and_details_as_owner(self):
        """Point 3: Customer can view their own order history and individual order details."""
        # 1. Login as Aarav Sharma (customer_id = 1)
        login_res = self.login_customer("aarav@gmail.com", "customer123")
        self.assertEqual(login_res.status_code, 200)

        # 2. Place order while logged in
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Takeaway',
            'payment_method': 'Simulated_UPI'
        })
        self.assertEqual(res.status_code, 201)
        order_id = res.get_json()['data']['order_id']

        # 3. View customer order history
        hist_res = self.client.get('/api/orders/history')
        self.assertEqual(hist_res.status_code, 200)
        hist_data = hist_res.get_json()
        self.assertTrue(hist_data['success'])
        self.assertGreater(hist_data['count'], 0)
        user_order_ids = [o['order_id'] for o in hist_data['data']]
        self.assertIn(order_id, user_order_ids)

        # 4. View single order details as owner
        det_res = self.client.get(f'/api/orders/{order_id}')
        self.assertEqual(det_res.status_code, 200)
        det_data = det_res.get_json()['data']
        self.assertEqual(det_data['order_id'], order_id)
        self.assertIn('items', det_data)
        self.assertIn('payment', det_data)
        self.assertIn('status_history', det_data)

    def test_04_idor_protection_customer_cannot_view_another_customer_order(self):
        """Point 4: One customer cannot access or tamper with another customer's order by modifying ID or URL."""
        # Order 1 placed by Aarav (customer_id = 1)
        self.login_customer("aarav@gmail.com", "customer123")
        res1 = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Takeaway',
            'payment_method': 'Simulated_UPI'
        })
        aarav_order_id = res1.get_json()['data']['order_id']
        aarav_order_ref = res1.get_json()['data']['order_reference']

        # Now login as Sneha Deshmukh (customer_id = 2)
        login2 = self.login_customer("sneha@gmail.com", "customer123")
        self.assertEqual(login2.status_code, 200)

        # Sneha attempts to access Aarav's order by changing ID in URL
        idor_res = self.client.get(f'/api/orders/{aarav_order_id}')
        self.assertEqual(idor_res.status_code, 403)
        self.assertIn("forbidden", idor_res.get_json()['message'].lower())

        # Sneha attempts to track Aarav's order via /api/orders/track/<ref>
        track_idor = self.client.get(f'/api/orders/track/{aarav_order_ref}')
        self.assertEqual(track_idor.status_code, 403)

        # Unauthenticated user attempting to access private order details
        self.client.post('/api/auth/logout')
        unauth_res = self.client.get(f'/api/orders/{aarav_order_id}')
        self.assertEqual(unauth_res.status_code, 401)

    def test_05_staff_searching_and_filtering_orders(self):
        """Point 5: Searching and filtering orders in the staff management interface."""
        self.login_staff("admin@cafenest.com", "admin123")

        # Filter by status = 'Confirmed'
        res = self.client.get('/api/orders?status=Confirmed')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        for o in data['data']:
            self.assertEqual(o['status'], 'Confirmed')

        # Filter by payment method = 'Cash'
        res_cash = self.client.get('/api/orders?payment_method=Cash')
        self.assertEqual(res_cash.status_code, 200)

        # Search query by term
        res_search = self.client.get('/api/orders?search=NEST')
        self.assertEqual(res_search.status_code, 200)
        self.assertTrue(res_search.get_json()['success'])

    def test_06_validated_status_transitions_and_rejection_of_invalid_transitions(self):
        """Point 6: Enforcing valid status transitions on the server and rejecting invalid transitions."""
        self.login_staff("admin@cafenest.com", "admin123")

        # Create fresh order with Cash (starts as Confirmed or Pending)
        # Let's insert a Pending order directly to test full transition pipeline
        test_ref = f"TEST-TRANS-{random.randint(100000, 999999)}"
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orders (order_reference, cafe_name, order_type, status, subtotal, tax_amount, total_amount)
                VALUES (%s, 'CaféNest Artisan Roastery', 'Takeaway', 'Pending', 190.00, 9.50, 199.50);
            """, (test_ref,))
            order_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Valid 1: Pending -> Confirmed
        r1 = self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Confirmed'})
        self.assertEqual(r1.status_code, 200)

        # Invalid: Confirmed -> Completed (skipping Preparing & Ready)
        r_inv = self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Completed'})
        self.assertEqual(r_inv.status_code, 400)
        self.assertIn("invalid status transition", r_inv.get_json()['message'].lower())

        # Valid 2: Confirmed -> Preparing
        r2 = self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Preparing'})
        self.assertEqual(r2.status_code, 200)

        # Valid 3: Preparing -> Ready
        r3 = self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Ready'})
        self.assertEqual(r3.status_code, 200)

        # Valid 4: Ready -> Completed (Terminal)
        r4 = self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Completed'})
        self.assertEqual(r4.status_code, 200)

        # Invalid: Completed -> Pending (cannot transition out of terminal state)
        r_term = self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Pending'})
        self.assertEqual(r_term.status_code, 400)

        # Verify audit trail in order_status_history
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT previous_status, new_status FROM order_status_history WHERE order_id = %s ORDER BY history_id;", (order_id,))
            history = cur.fetchall()
            self.assertEqual(len(history), 4)
            self.assertEqual(history[0]['new_status'], 'Confirmed')
            self.assertEqual(history[1]['new_status'], 'Preparing')
            self.assertEqual(history[2]['new_status'], 'Ready')
            self.assertEqual(history[3]['new_status'], 'Completed')
        conn.close()

    def test_07_unauthorized_users_cannot_update_order_statuses(self):
        """Point 7: Customers or unauthenticated users cannot update order statuses."""
        # 1. Unauthenticated
        self.client.post('/api/auth/logout')
        res = self.client.post('/api/orders/update-status', json={'order_id': 1, 'status': 'Completed'})
        self.assertEqual(res.status_code, 403)

        # 2. Customer user (not staff)
        self.login_customer("aarav@gmail.com", "customer123")
        res_cust = self.client.post('/api/orders/update-status', json={'order_id': 1, 'status': 'Completed'})
        self.assertEqual(res_cust.status_code, 403)

    def test_08_cash_payment_selection_and_pending_status(self):
        """Point 8: Selecting Cash stores status 'Pending' and can be confirmed by authorized staff."""
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Takeaway',
            'payment_method': 'Cash'
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()['data']
        order_id = data['order_id']
        self.assertEqual(data['payment']['method'], 'Cash')
        self.assertEqual(data['payment']['status'], 'Pending')

        # Check in MySQL
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT method, status FROM payments WHERE order_id = %s;", (order_id,))
            p = cur.fetchone()
            self.assertEqual(p['method'], 'Cash')
            self.assertEqual(p['status'], 'Pending')
        conn.close()

        # Staff confirms cash collection
        self.login_staff("admin@cafenest.com", "admin123")
        confirm_res = self.client.post('/api/payments/confirm-cash', json={'order_id': order_id})
        self.assertEqual(confirm_res.status_code, 200)
        self.assertEqual(confirm_res.get_json()['data']['status'], 'Completed')

        # Verify payment is now Completed in MySQL
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM payments WHERE order_id = %s;", (order_id,))
            p2 = cur.fetchone()
            self.assertEqual(p2['status'], 'Completed')
        conn.close()

    def test_09_simulated_upi_demonstration_flow(self):
        """Point 9: Completing Simulated UPI flow records simulation disclaimer and demo status."""
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 2, 'quantity': 1}], # 210.00
            'order_type': 'Takeaway',
            'payment_method': 'Simulated_UPI'
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()['data']
        order_id = data['order_id']

        # Process / verify simulated UPI via payments endpoint
        pay_res = self.client.post('/api/payments/pay', json={
            'order_id': order_id,
            'method': 'Simulated_UPI',
            'upi_id': 'aarav@okaxis'
        })
        self.assertEqual(pay_res.status_code, 200)
        pay_data = pay_res.get_json()
        self.assertTrue(pay_data['data']['is_simulated'])
        self.assertIn("College DBMS Lab Demonstration Mode", pay_data['data']['disclaimer'])

    def test_10_reject_invalid_payments_and_nonexistent_orders(self):
        """Point 10: Rejecting invalid payment requests, tampered amounts, and nonexistent orders."""
        # 1. Nonexistent order ID
        r1 = self.client.post('/api/payments/pay', json={'order_id': 999999, 'method': 'Simulated_UPI'})
        self.assertEqual(r1.status_code, 404)

        # 2. Invalid payment method
        r2 = self.client.post('/api/payments/pay', json={'order_id': 1, 'method': 'Bitcoin'})
        self.assertEqual(r2.status_code, 400)

        # 3. Tampered amount mismatch
        res_order = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Takeaway',
            'payment_method': 'Cash'
        })
        o_id = res_order.get_json()['data']['order_id']
        r3 = self.client.post('/api/payments/pay', json={
            'order_id': o_id,
            'method': 'Simulated_UPI',
            'amount': 1.00 # tampered amount vs server 199.50
        })
        self.assertEqual(r3.status_code, 400)
        self.assertIn("mismatch", r3.get_json()['message'].lower())

    def test_11_consistency_between_orders_items_and_payments(self):
        """Point 11: Absolute consistency between order header totals, line items sum, and payments table."""
        res = self.client.post('/api/orders', json={
            'items': [
                {'menu_id': 1, 'quantity': 3}, # 190.00 * 3 = 570.00
                {'menu_id': 2, 'quantity': 2}  # 210.00 * 2 = 420.00
            ],
            'order_type': 'Takeaway',
            'payment_method': 'Simulated_UPI'
        })
        self.assertEqual(res.status_code, 201)
        order_id = res.get_json()['data']['order_id']

        conn = get_db_connection()
        with conn.cursor() as cur:
            # Header
            cur.execute("SELECT subtotal, tax_amount, total_amount FROM orders WHERE order_id = %s;", (order_id,))
            order_hdr = cur.fetchone()

            # Line items sum
            cur.execute("SELECT SUM(subtotal) as items_sum FROM order_details WHERE order_id = %s;", (order_id,))
            items_sum = float(cur.fetchone()['items_sum'])

            # Payment record
            cur.execute("SELECT amount FROM payments WHERE order_id = %s;", (order_id,))
            pay_row = cur.fetchone()
            pay_amount = float(pay_row['amount'])

            # Subtotal consistency
            self.assertEqual(float(order_hdr['subtotal']), 990.00)
            self.assertEqual(items_sum, 990.00)

            # Tax and Grand Total consistency (990 + 49.50 = 1039.50)
            self.assertEqual(float(order_hdr['tax_amount']), 49.50)
            self.assertEqual(float(order_hdr['total_amount']), 1039.50)
            self.assertEqual(pay_amount, 1039.50)
        conn.close()

    def test_12_and_13_persistence_and_refresh_verification(self):
        """Points 12 & 13: Order, payment, and status audit data persist in MySQL and refresh accurately."""
        # Place order
        res = self.client.post('/api/orders', json={
            'items': [{'menu_id': 1, 'quantity': 1}],
            'order_type': 'Takeaway',
            'payment_method': 'Cash'
        })
        order_id = res.get_json()['data']['order_id']
        order_ref = res.get_json()['data']['order_reference']

        # Transition status
        self.login_staff("admin@cafenest.com", "admin123")
        self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Confirmed', 'notes': 'Barista started'})

        # Confirm cash
        self.client.post('/api/payments/confirm-cash', json={'order_id': order_id})

        # Advance to Preparing
        self.client.post('/api/orders/update-status', json={'order_id': order_id, 'status': 'Preparing'})

        # Directly query MySQL (simulating restart / fresh connection)
        fresh_conn = get_db_connection()
        with fresh_conn.cursor() as cur:
            cur.execute("SELECT status FROM orders WHERE order_id = %s;", (order_id,))
            fresh_order = cur.fetchone()
            self.assertEqual(fresh_order['status'], 'Preparing')

            cur.execute("SELECT status FROM payments WHERE order_id = %s;", (order_id,))
            fresh_pay = cur.fetchone()
            self.assertEqual(fresh_pay['status'], 'Completed')

            cur.execute("SELECT COUNT(*) as cnt FROM order_status_history WHERE order_id = %s;", (order_id,))
            h_count = cur.fetchone()['cnt']
            self.assertGreaterEqual(h_count, 2)
        fresh_conn.close()

        # Customer tracking refresh verification
        track_res = self.client.get(f'/api/orders/track/{order_ref}')
        self.assertEqual(track_res.status_code, 200)
        track_data = track_res.get_json()['data']
        self.assertEqual(track_data['status'], 'Preparing')
        self.assertEqual(track_data['payment']['status'], 'Completed')

if __name__ == '__main__':
    unittest.main()
