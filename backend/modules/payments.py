import random
import string
from flask import Blueprint, request, jsonify
from backend.config.db_config import get_db_connection

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/demo', methods=['POST'])
def process_simulated_payment():
    """
    Demonstration payment recording for college DBMS demonstration.
    Does NOT process actual money or connect to real banks.
    Saves record to MySQL 'payments' table with 'is_simulated = TRUE'.
    """
    data = request.get_json() or {}
    order_id = data.get('order_id')
    method = data.get('method', 'Simulated_UPI')  # 'Cash' or 'Simulated_UPI'
    upi_id = data.get('upi_id', '').strip()

    if not order_id:
        return jsonify({'success': False, 'message': 'order_id is required.'}), 400

    if method not in ('Cash', 'Simulated_UPI'):
        return jsonify({'success': False, 'message': 'Invalid demonstration payment method.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT order_id, total_amount, status, order_reference FROM orders WHERE order_id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': 'Order not found.'}), 404

            amount = float(order['total_amount'])

            # Generate realistic demo transaction reference
            rand_code = ''.join(random.choices(string.digits, k=8))
            if method == 'Simulated_UPI':
                tx_ref = f"UPI-DEMO-{rand_code}"
            else:
                tx_ref = f"CASH-REC-{rand_code}"

            cur.execute("""
                INSERT INTO payments (order_id, amount, method, status, transaction_ref, is_simulated)
                VALUES (%s, %s, %s, 'Completed', %s, TRUE);
            """, (order_id, amount, method, tx_ref))
            payment_id = cur.lastrowid

            # Update order status to Confirmed if it was Pending
            if order['status'] == 'Pending':
                cur.execute("UPDATE orders SET status = 'Confirmed' WHERE order_id = %s;", (order_id,))

            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Simulated payment confirmed! Your order is now being processed by the kitchen.',
                'data': {
                    'payment_id': payment_id,
                    'order_id': order_id,
                    'order_reference': order['order_reference'],
                    'amount': amount,
                    'method': method,
                    'transaction_ref': tx_ref,
                    'status': 'Completed',
                    'is_simulated': True,
                    'disclaimer': 'College Lab Demonstration Mode — No actual financial transaction occurred.'
                }
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Simulated payment recording failed: {str(e)}'}), 500
    finally:
        conn.close()
