import random
import string
from flask import Blueprint, request, jsonify, session
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

orders_bp = Blueprint('orders', __name__)

VALID_STATUSES = ['Pending', 'Confirmed', 'Preparing', 'Ready', 'Completed', 'Cancelled']

def generate_order_reference():
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=5))
    return f"NEST-{suffix}"

@orders_bp.route('', methods=['POST'])
def place_order():
    """
    Validates cart and places an order strictly enforcing server-side business rules:
    - Database transaction ensures consistency
    - Prices re-fetched from DB
    - Quantity > 0 checked
    - Item availability verified
    """
    data = request.get_json() or {}
    cart_items = data.get('items', [])
    order_type = data.get('order_type', 'Dine-In')
    table_id = data.get('table_id')
    special_instructions = data.get('special_instructions', '').strip()

    if order_type not in ('Dine-In', 'Takeaway'):
        return jsonify({'success': False, 'message': 'Invalid order type. Choose Dine-In or Takeaway.'}), 400

    if not cart_items or not isinstance(cart_items, list) or len(cart_items) == 0:
        return jsonify({'success': False, 'message': 'Cannot place an empty order. Please add items to your cart.'}), 400

    # User identification: from session if logged in
    customer_id = session.get('user_id') if session.get('user_type') == 'customer' else None

    # If Dine-In, table_id should be checked if supplied
    if order_type == 'Dine-In' and not table_id:
        return jsonify({'success': False, 'message': 'Please select a table number for Dine-In orders.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Verify table if Dine-In
            if order_type == 'Dine-In' and table_id:
                cur.execute("SELECT table_id, table_number, status FROM cafe_tables WHERE table_id = %s;", (table_id,))
                table = cur.fetchone()
                if not table:
                    return jsonify({'success': False, 'message': 'Selected table does not exist.'}), 400

            # 2. Extract item IDs and quantities, validating each
            item_quantities = {}
            for entry in cart_items:
                m_id = entry.get('menu_id')
                qty = entry.get('quantity')
                if not m_id or not isinstance(qty, int) or qty <= 0:
                    return jsonify({'success': False, 'message': 'Invalid item or quantity. Quantities must be positive integers.'}), 400
                item_quantities[int(m_id)] = item_quantities.get(int(m_id), 0) + qty

            # 3. Query all items in one batch to verify existence, availability, and trusted price
            menu_ids = list(item_quantities.keys())
            format_strings = ','.join(['%s'] * len(menu_ids))
            cur.execute(f"""
                SELECT menu_id, name, price, is_available
                FROM menu
                WHERE menu_id IN ({format_strings});
            """, menu_ids)
            db_items = {row['menu_id']: row for row in cur.fetchall()}

            if len(db_items) != len(menu_ids):
                return jsonify({'success': False, 'message': 'One or more items in your cart do not exist.'}), 400

            # Check availability & compute trusted subtotal
            computed_subtotal = 0.0
            order_line_items = []
            for m_id, qty in item_quantities.items():
                item = db_items[m_id]
                if not bool(item['is_available']):
                    return jsonify({'success': False, 'message': f"Sorry, '{item['name']}' is currently sold out / unavailable."}), 400

                unit_price = float(item['price'])
                line_subtotal = round(unit_price * qty, 2)
                computed_subtotal += line_subtotal
                order_line_items.append({
                    'menu_id': m_id,
                    'quantity': qty,
                    'unit_price': unit_price,
                    'subtotal': line_subtotal
                })

            computed_subtotal = round(computed_subtotal, 2)
            tax_rate = 0.05  # 5% GST
            tax_amount = round(computed_subtotal * tax_rate, 2)
            total_amount = round(computed_subtotal + tax_amount, 2)

            # Generate unique order reference
            order_ref = generate_order_reference()

            # Insert order header
            cur.execute("""
                INSERT INTO orders (order_reference, customer_id, table_id, order_type, status, subtotal, tax_amount, total_amount, special_instructions)
                VALUES (%s, %s, %s, %s, 'Pending', %s, %s, %s, %s);
            """, (order_ref, customer_id, table_id if order_type == 'Dine-In' else None, order_type, computed_subtotal, tax_amount, total_amount, special_instructions))
            order_id = cur.lastrowid

            # Insert order details
            for item in order_line_items:
                cur.execute("""
                    INSERT INTO order_details (order_id, menu_id, quantity, unit_price, subtotal)
                    VALUES (%s, %s, %s, %s, %s);
                """, (order_id, item['menu_id'], item['quantity'], item['unit_price'], item['subtotal']))

            # Update table status to Occupied if Dine-In
            if order_type == 'Dine-In' and table_id:
                cur.execute("UPDATE cafe_tables SET status = 'Occupied' WHERE table_id = %s;", (table_id,))

            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Order placed successfully! Please proceed to simulated payment.',
                'data': {
                    'order_id': order_id,
                    'order_reference': order_ref,
                    'order_type': order_type,
                    'table_id': table_id,
                    'subtotal': computed_subtotal,
                    'tax_amount': tax_amount,
                    'total_amount': total_amount,
                    'status': 'Pending'
                }
            }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Failed to place order: {str(e)}'}), 500
    finally:
        conn.close()

@orders_bp.route('', methods=['GET'])
def list_orders():
    """Returns order list based on caller role: customer sees theirs, staff/admin sees all."""
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    status_filter = request.args.get('status')
    limit = int(request.args.get('limit', 50))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT o.order_id, o.order_reference, o.customer_id, o.table_id,
                       o.order_type, o.status, o.subtotal, o.tax_amount, o.total_amount,
                       o.special_instructions, o.created_at,
                       t.table_number,
                       c.name as customer_name, c.phone as customer_phone,
                       p.method as payment_method, p.status as payment_status
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                LEFT JOIN payments p ON o.order_id = p.order_id
                WHERE 1=1
            """
            params = []

            # If customer, restrict to their customer_id
            if user_type == 'customer':
                sql += " AND o.customer_id = %s"
                params.append(user_id)
            elif user_type != 'staff':
                # Guest or unauthenticated viewing recent demo orders
                guest_ref = request.args.get('ref')
                if guest_ref:
                    sql += " AND o.order_reference = %s"
                    params.append(guest_ref)
                else:
                    return jsonify({'success': True, 'data': []})

            if status_filter and status_filter in VALID_STATUSES:
                sql += " AND o.status = %s"
                params.append(status_filter)

            sql += " ORDER BY o.created_at DESC LIMIT %s;"
            params.append(limit)

            cur.execute(sql, params)
            orders = cur.fetchall()

            for ord_row in orders:
                ord_row['subtotal'] = float(ord_row['subtotal'])
                ord_row['tax_amount'] = float(ord_row['tax_amount'])
                ord_row['total_amount'] = float(ord_row['total_amount'])
                ord_row['created_at'] = ord_row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if ord_row['created_at'] else ''

            return jsonify({'success': True, 'count': len(orders), 'data': orders})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching orders: {str(e)}'}), 500
    finally:
        conn.close()

@orders_bp.route('/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.order_id, o.order_reference, o.customer_id, o.table_id,
                       o.order_type, o.status, o.subtotal, o.tax_amount, o.total_amount,
                       o.special_instructions, o.created_at,
                       t.table_number, t.location_area,
                       c.name as customer_name, c.email as customer_email, c.phone as customer_phone
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_id = %s;
            """, (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': 'Order not found.'}), 404

            # Permission check: customer can only view own order, staff can view any
            user_type = session.get('user_type')
            user_id = session.get('user_id')
            if user_type == 'customer' and order['customer_id'] and order['customer_id'] != user_id:
                return jsonify({'success': False, 'message': 'Unauthorized to view this order.'}), 403

            order['subtotal'] = float(order['subtotal'])
            order['tax_amount'] = float(order['tax_amount'])
            order['total_amount'] = float(order['total_amount'])
            order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M:%S') if order['created_at'] else ''

            # Fetch line items
            cur.execute("""
                SELECT od.order_detail_id, od.menu_id, od.quantity, od.unit_price, od.subtotal,
                       m.name as item_name, m.image_url, m.is_veg
                FROM order_details od
                JOIN menu m ON od.menu_id = m.menu_id
                WHERE od.order_id = %s;
            """, (order_id,))
            items = cur.fetchall()
            for it in items:
                it['unit_price'] = float(it['unit_price'])
                it['subtotal'] = float(it['subtotal'])
                it['is_veg'] = bool(it['is_veg'])
            order['items'] = items

            # Fetch payment record if any
            cur.execute("""
                SELECT payment_id, amount, method, status, transaction_ref, is_simulated, paid_at
                FROM payments WHERE order_id = %s ORDER BY payment_id DESC LIMIT 1;
            """, (order_id,))
            payment = cur.fetchone()
            if payment:
                payment['amount'] = float(payment['amount'])
                payment['paid_at'] = payment['paid_at'].strftime('%Y-%m-%d %H:%M:%S') if payment['paid_at'] else ''
            order['payment'] = payment

            return jsonify({'success': True, 'data': order})
    finally:
        conn.close()

@orders_bp.route('/track/<reference>', methods=['GET'])
def track_order_by_ref(reference):
    """Allows public tracking by reference code e.g. NEST-XXXX."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.order_id, o.order_reference, o.order_type, o.status,
                       o.subtotal, o.tax_amount, o.total_amount, o.created_at,
                       t.table_number, t.location_area
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                WHERE o.order_reference = %s;
            """, (reference.strip(),))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': f'Order reference {reference} not found.'}), 404

            order['subtotal'] = float(order['subtotal'])
            order['tax_amount'] = float(order['tax_amount'])
            order['total_amount'] = float(order['total_amount'])
            order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M:%S') if order['created_at'] else ''

            # Fetch items
            cur.execute("""
                SELECT od.quantity, od.unit_price, od.subtotal, m.name as item_name
                FROM order_details od
                JOIN menu m ON od.menu_id = m.menu_id
                WHERE od.order_id = %s;
            """, (order['order_id'],))
            items = cur.fetchall()
            for it in items:
                it['unit_price'] = float(it['unit_price'])
                it['subtotal'] = float(it['subtotal'])
            order['items'] = items

            # Payment
            cur.execute("SELECT method, status, transaction_ref FROM payments WHERE order_id = %s;", (order['order_id'],))
            order['payment'] = cur.fetchone()

            return jsonify({'success': True, 'data': order})
    finally:
        conn.close()

@orders_bp.route('/update-status', methods=['POST'])
@staff_required
def update_order_status():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    new_status = data.get('status')

    if not order_id or not new_status:
        return jsonify({'success': False, 'message': 'order_id and status are required.'}), 400

    if new_status not in VALID_STATUSES:
        return jsonify({'success': False, 'message': f'Invalid status. Allowed: {", ".join(VALID_STATUSES)}'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT order_id, order_reference, table_id, status FROM orders WHERE order_id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': 'Order not found.'}), 404

            cur.execute("UPDATE orders SET status = %s WHERE order_id = %s;", (new_status, order_id))

            # If order reached Completed or Cancelled, free up the table
            if new_status in ('Completed', 'Cancelled') and order['table_id']:
                cur.execute("UPDATE cafe_tables SET status = 'Available' WHERE table_id = %s;", (order['table_id'],))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Order #{order['order_reference']} status updated to {new_status}.",
                'data': {'order_id': order_id, 'status': new_status}
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Status update failed: {str(e)}'}), 500
    finally:
        conn.close()
