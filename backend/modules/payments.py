import random
import string
from flask import Blueprint, request, jsonify, session
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

payments_bp = Blueprint('payments', __name__)

DEMO_DISCLAIMER = "College DBMS Lab Demonstration Mode — Simulated Payment Only. No real money or bank accounts are accessed."

@payments_bp.route('/pay', methods=['POST'])
@payments_bp.route('/demo', methods=['POST'])
def process_simulated_payment():
    """
    Demonstration payment recording for college DBMS project.
    Strictly enforces:
    - Order existence check (404 on nonexistent order)
    - Customer ownership & authorization (403 on IDOR)
    - Server-side amount validation against orders.total_amount
    - Duplicate payment prevention (rejects if already Completed)
    - Dual methods: Simulated_UPI (Completed) and Cash (Pending until staff settlement)
    - Records transaction in MySQL 'payments' table with is_simulated = TRUE
    """
    data = request.get_json() or {}
    order_id = data.get('order_id')
    method = data.get('method', 'Simulated_UPI')  # 'Simulated_UPI' or 'Cash'
    upi_id = data.get('upi_id', '').strip()
    client_amount = data.get('amount')

    if not order_id:
        return jsonify({'success': False, 'message': 'order_id is required.'}), 400

    try:
        order_id = int(order_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid order_id format.'}), 400

    if method not in ('Cash', 'Simulated_UPI'):
        return jsonify({'success': False, 'message': "Invalid payment method. Must be 'Cash' or 'Simulated_UPI'."}), 400

    user_type = session.get('user_type')
    user_id = session.get('user_id')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Fetch order and verify existence
            cur.execute("""
                SELECT order_id, order_reference, customer_id, total_amount, status
                FROM orders
                WHERE order_id = %s;
            """, (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': f'Order ID {order_id} not found.'}), 404

            # 2. Authorization check (IDOR protection)
            if user_type == 'customer' and order['customer_id'] and order['customer_id'] != user_id:
                return jsonify({'success': False, 'message': 'Forbidden: You do not have permission to pay for this order.'}), 403

            server_total = float(order['total_amount'])

            # 3. Reject client-supplied amount tampering if client explicitly provided an amount
            if client_amount is not None:
                try:
                    c_amount = round(float(client_amount), 2)
                    if c_amount != server_total:
                        return jsonify({
                            'success': False,
                            'message': f"Payment amount mismatch. Order total is ₹{server_total:.2f}, but client sent ₹{c_amount:.2f}."
                        }), 400
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Invalid amount value.'}), 400

            # 4. Check for existing payments for this order
            cur.execute("""
                SELECT payment_id, method, status, amount, transaction_ref, paid_at
                FROM payments
                WHERE order_id = %s
                ORDER BY payment_id DESC LIMIT 1;
            """, (order_id,))
            existing_payment = cur.fetchone()

            if existing_payment and existing_payment['status'] == 'Completed':
                return jsonify({
                    'success': True,
                    'is_duplicate': True,
                    'message': 'Payment has already been completed for this order.',
                    'data': {
                        'payment_id': existing_payment['payment_id'],
                        'order_id': order_id,
                        'order_reference': order['order_reference'],
                        'amount': float(existing_payment['amount']),
                        'method': existing_payment['method'],
                        'transaction_ref': existing_payment['transaction_ref'],
                        'status': existing_payment['status'],
                        'is_simulated': True,
                        'disclaimer': DEMO_DISCLAIMER
                    }
                }), 200

            # 5. Determine status and transaction reference
            rand_code = ''.join(random.choices(string.digits, k=8))
            if method == 'Simulated_UPI':
                tx_ref = f"UPI-DEMO-{rand_code}"
                pay_status = 'Completed'
                msg = 'Simulated UPI payment confirmed! Your order is now confirmed in the kitchen.'
            else:
                tx_ref = f"CASH-REC-{rand_code}"
                pay_status = 'Pending'
                msg = 'Cash payment recorded as Pending. Please present Order Reference at counter or upon table service.'

            # 6. Insert or update payment record
            if existing_payment and existing_payment['status'] != 'Completed':
                # Update existing pending payment record
                cur.execute("""
                    UPDATE payments
                    SET method = %s, status = %s, transaction_ref = %s, amount = %s, paid_at = CURRENT_TIMESTAMP
                    WHERE payment_id = %s;
                """, (method, pay_status, tx_ref, server_total, existing_payment['payment_id']))
                payment_id = existing_payment['payment_id']
            else:
                # Insert fresh payment record
                cur.execute("""
                    INSERT INTO payments (order_id, amount, method, status, transaction_ref, is_simulated)
                    VALUES (%s, %s, %s, %s, %s, TRUE);
                """, (order_id, server_total, method, pay_status, tx_ref))
                payment_id = cur.lastrowid

            # 7. Update order status to Confirmed if it was Pending
            if order['status'] == 'Pending':
                cur.execute("UPDATE orders SET status = 'Confirmed' WHERE order_id = %s;", (order_id,))
                cur.execute("""
                    INSERT INTO order_status_history (order_id, previous_status, new_status, changed_by_staff_id, notes)
                    VALUES (%s, 'Pending', 'Confirmed', %s, %s);
                """, (order_id, session.get('user_id') if user_type == 'staff' else None, f"Status updated upon payment ({method})"))

            conn.commit()

            return jsonify({
                'success': True,
                'message': msg,
                'data': {
                    'payment_id': payment_id,
                    'order_id': order_id,
                    'order_reference': order['order_reference'],
                    'amount': server_total,
                    'method': method,
                    'transaction_ref': tx_ref,
                    'status': pay_status,
                    'is_simulated': True,
                    'disclaimer': DEMO_DISCLAIMER
                }
            }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Payment recording failed: {str(e)}'}), 500
    finally:
        conn.close()

@payments_bp.route('/confirm-cash', methods=['POST'])
@staff_required
def confirm_cash_payment():
    """
    Staff-only workflow: confirms receipt of cash for an order.
    Transitions payment status from 'Pending' to 'Completed'.
    """
    data = request.get_json() or {}
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({'success': False, 'message': 'order_id is required.'}), 400

    staff_id = session.get('user_id')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.payment_id, p.order_id, p.amount, p.method, p.status, p.transaction_ref,
                       o.order_reference
                FROM payments p
                JOIN orders o ON p.order_id = o.order_id
                WHERE p.order_id = %s
                ORDER BY p.payment_id DESC LIMIT 1;
            """, (order_id,))
            payment = cur.fetchone()

            if not payment:
                return jsonify({'success': False, 'message': 'No payment record found for this order.'}), 404

            if payment['status'] == 'Completed':
                return jsonify({
                    'success': True,
                    'message': 'Payment has already been marked as Completed.',
                    'data': {
                        'payment_id': payment['payment_id'],
                        'order_id': order_id,
                        'order_reference': payment['order_reference'],
                        'status': 'Completed'
                    }
                }), 200

            # Update payment status to Completed
            cur.execute("""
                UPDATE payments
                SET status = 'Completed', paid_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s;
            """, (payment['payment_id'],))

            # Record in order status history
            cur.execute("""
                INSERT INTO order_status_history (order_id, previous_status, new_status, changed_by_staff_id, notes)
                VALUES (%s, 'Payment_Pending', 'Payment_Completed', %s, 'Cash payment confirmed by staff');
            """, (order_id, staff_id))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Cash payment for Order #{payment['order_reference']} confirmed by staff.",
                'data': {
                    'payment_id': payment['payment_id'],
                    'order_id': order_id,
                    'order_reference': payment['order_reference'],
                    'amount': float(payment['amount']),
                    'method': 'Cash',
                    'status': 'Completed',
                    'transaction_ref': payment['transaction_ref'],
                    'is_simulated': True
                }
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Confirm cash failed: {str(e)}'}), 500
    finally:
        conn.close()

@payments_bp.route('/<int:order_id>', methods=['GET'])
def get_payment_details(order_id):
    """Returns payment information for an order with authorization check."""
    user_type = session.get('user_type')
    user_id = session.get('user_id')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.payment_id, p.order_id, p.amount, p.method, p.status,
                       p.transaction_ref, p.is_simulated, p.paid_at,
                       o.customer_id, o.order_reference, o.total_amount
                FROM payments p
                JOIN orders o ON p.order_id = o.order_id
                WHERE p.order_id = %s
                ORDER BY p.payment_id DESC LIMIT 1;
            """, (order_id,))
            payment = cur.fetchone()
            if not payment:
                return jsonify({'success': False, 'message': 'Payment record not found.'}), 404

            # Authorization check
            if user_type == 'customer' and payment['customer_id'] and payment['customer_id'] != user_id:
                return jsonify({'success': False, 'message': 'Forbidden.'}), 403

            payment['amount'] = float(payment['amount'])
            payment['total_amount'] = float(payment['total_amount'])
            payment['paid_at'] = payment['paid_at'].strftime('%Y-%m-%d %H:%M:%S') if payment['paid_at'] else ''
            payment['is_simulated'] = bool(payment['is_simulated'])
            payment['disclaimer'] = DEMO_DISCLAIMER

            return jsonify({'success': True, 'data': payment})
    finally:
        conn.close()
