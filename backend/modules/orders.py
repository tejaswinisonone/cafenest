import random
import string
from flask import Blueprint, request, jsonify, session
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required, customer_required

orders_bp = Blueprint('orders', __name__)

VALID_STATUSES = ['Pending', 'Confirmed', 'Preparing', 'Ready', 'Completed', 'Cancelled']

# Enforced server-side status transition state machine
VALID_TRANSITIONS = {
    'Pending': ['Confirmed', 'Cancelled'],
    'Confirmed': ['Preparing', 'Cancelled'],
    'Preparing': ['Ready', 'Cancelled'],
    'Ready': ['Completed', 'Cancelled'],
    'Completed': [],    # Terminal state
    'Cancelled': []     # Terminal state
}

def generate_order_reference():
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=5))
    return f"NEST-{suffix}"

@orders_bp.route('', methods=['POST'])
def place_order():
    """
    Validates cart and places an order strictly enforcing server-side business rules:
    - Checks and prevents duplicate submissions (via idempotency_key)
    - Validates cart is non-empty
    - Validates all quantities are positive integers (> 0)
    - Validates all items exist and are currently available in SQL
    - Validates table existence and availability if Dine-In
    - Disregards client-submitted totals; re-reads trusted prices from SQL and recalculates subtotal, 5% GST, and total
    - Executes order creation, order details, table status update, simulated payment, and status history inside an ACID SQL transaction
    - Rolls back the transaction on any error
    """
    data = request.get_json() or {}
    cart_items = data.get('items', [])
    order_type = data.get('order_type', 'Dine-In')
    table_id = data.get('table_id')
    special_instructions = data.get('special_instructions', '').strip()
    idempotency_key = data.get('idempotency_key', '').strip() or None
    payment_method = data.get('payment_method', 'Simulated_UPI')  # 'Simulated_UPI' or 'Cash'
    
    # Customer contact details (from request body or session)
    customer_name = data.get('customer_name', '').strip()
    customer_phone = data.get('customer_phone', '').strip()
    customer_email = data.get('customer_email', '').strip().lower()

    # User identification from session if logged in
    customer_id = session.get('user_id') if session.get('user_type') == 'customer' else None
    if not customer_name and session.get('user_name'):
        customer_name = session.get('user_name')
    if not customer_email and session.get('user_email'):
        customer_email = session.get('user_email')

    party_size = data.get('party_size')
    if party_size is not None:
        try:
            party_size = int(party_size)
            if party_size <= 0:
                return jsonify({'success': False, 'message': 'party_size must be a positive integer (> 0).'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid party_size format.'}), 400
    else:
        party_size = 1

    # 1. Validate order type
    if order_type not in ('Dine-In', 'Takeaway'):
        return jsonify({'success': False, 'message': 'Invalid order type. Choose Dine-In or Takeaway.'}), 400

    # 2. Validate cart items presence
    if not cart_items or not isinstance(cart_items, list) or len(cart_items) == 0:
        return jsonify({'success': False, 'message': 'Cannot place an empty order. Please add items to your cart.'}), 400

    # 3. Validate payment method
    if payment_method not in ('Simulated_UPI', 'Cash'):
        return jsonify({'success': False, 'message': 'Invalid payment method. Choose Simulated_UPI or Cash.'}), 400

    # 4. If Dine-In, table_id is required
    if order_type == 'Dine-In':
        if not table_id:
            return jsonify({'success': False, 'message': 'Please select a table number for Dine-In orders.'}), 400
        try:
            table_id = int(table_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid table identifier.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check for duplicate submission via idempotency_key
            if idempotency_key:
                cur.execute("""
                    SELECT o.order_id, o.order_reference, o.status, o.total_amount, o.created_at
                    FROM orders o
                    WHERE o.idempotency_key = %s;
                """, (idempotency_key,))
                existing_order = cur.fetchone()
                if existing_order:
                    # Return existing order preventing duplicate insert
                    return jsonify({
                        'success': True,
                        'is_duplicate': True,
                        'message': 'Order already processed (duplicate submission prevented).',
                        'data': {
                            'order_id': existing_order['order_id'],
                            'order_reference': existing_order['order_reference'],
                            'status': existing_order['status'],
                            'total_amount': float(existing_order['total_amount'])
                        }
                    }), 200

            # 5. Verify table existence, party capacity, and status with concurrency lock (FOR UPDATE)
            if order_type == 'Dine-In':
                cur.execute("""
                    SELECT table_id, table_number, seating_capacity, status, cafe_name
                    FROM cafe_tables
                    WHERE table_id = %s
                    FOR UPDATE;
                """, (table_id,))
                table = cur.fetchone()
                if not table:
                    return jsonify({'success': False, 'message': 'Selected table does not exist.'}), 400
                if table['status'] != 'Available':
                    return jsonify({'success': False, 'message': f"Table '{table['table_number']}' is currently {table['status']}. Please select an available table."}), 400
                if party_size and table['seating_capacity'] < party_size:
                    return jsonify({'success': False, 'message': f"Table '{table['table_number']}' has capacity for {table['seating_capacity']} guest(s), but party size is {party_size}."}), 400

            # 6. Extract item IDs and quantities, validating each strictly
            item_quantities = {}
            for entry in cart_items:
                if not isinstance(entry, dict):
                    return jsonify({'success': False, 'message': 'Malformed cart items data.'}), 400
                m_id = entry.get('menu_id')
                qty = entry.get('quantity')

                # Check quantity is valid positive integer
                if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                    return jsonify({'success': False, 'message': 'Invalid item or quantity. Quantities must be positive integers.'}), 400

                try:
                    m_id = int(m_id)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Invalid menu item ID.'}), 400

                item_quantities[m_id] = item_quantities.get(m_id, 0) + qty

            # 7. Query all items in one batch from SQL to get authoritative prices & availability
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

            # Check availability and calculate trusted totals on Python backend
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
                    'name': item['name'],
                    'quantity': qty,
                    'unit_price': unit_price,
                    'subtotal': line_subtotal
                })

            computed_subtotal = round(computed_subtotal, 2)
            tax_rate = 0.05  # 5% GST
            tax_amount = round(computed_subtotal * tax_rate, 2)
            discount_amount = 0.00
            total_amount = round(computed_subtotal + tax_amount - discount_amount, 2)

            # Generate unique order reference
            order_ref = generate_order_reference()

            # Status determination:
            # If payment is Simulated_UPI, immediate Confirmed
            # If Cash, Confirmed for kitchen preparation with payment pending
            initial_status = 'Confirmed'

            # 8. Insert Order Header in transaction
            cur.execute("""
                INSERT INTO orders (
                    order_reference, cafe_name, customer_id, customer_name, customer_phone, customer_email,
                    table_id, party_size, order_type, status, subtotal, tax_amount, discount_amount, total_amount,
                    special_instructions, idempotency_key
                )
                VALUES (%s, 'CaféNest Artisan Roastery', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                order_ref, customer_id, customer_name, customer_phone, customer_email,
                table_id if order_type == 'Dine-In' else None,
                party_size if order_type == 'Dine-In' else 1,
                order_type, initial_status,
                computed_subtotal, tax_amount, discount_amount, total_amount,
                special_instructions, idempotency_key
            ))
            order_id = cur.lastrowid

            # 9. Insert Order Details (line items with snapshot item_name)
            for item in order_line_items:
                cur.execute("""
                    INSERT INTO order_details (order_id, menu_id, item_name, quantity, unit_price, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (order_id, item['menu_id'], item['name'], item['quantity'], item['unit_price'], item['subtotal']))

            # 10. Update table status to Occupied if Dine-In
            if order_type == 'Dine-In' and table_id:
                cur.execute("UPDATE cafe_tables SET status = 'Occupied' WHERE table_id = %s;", (table_id,))

            # 11. Create Payment record inside the transaction
            rand_code = ''.join(random.choices(string.digits, k=8))
            if payment_method == 'Simulated_UPI':
                tx_ref = f"UPI-DEMO-{rand_code}"
                pay_status = 'Completed'
            else:
                tx_ref = f"CASH-REC-{rand_code}"
                pay_status = 'Pending'

            cur.execute("""
                INSERT INTO payments (order_id, amount, method, status, transaction_ref, is_simulated)
                VALUES (%s, %s, %s, %s, %s, TRUE);
            """, (order_id, total_amount, payment_method, pay_status, tx_ref))
            payment_id = cur.lastrowid

            # 12. Record initial status in order_status_history
            cur.execute("""
                INSERT INTO order_status_history (order_id, previous_status, new_status, changed_by_staff_id, notes)
                VALUES (%s, NULL, %s, NULL, %s);
            """, (order_id, initial_status, f"Order placed via online checkout ({payment_method})"))

            # Commit the entire transaction atomically
            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Order created and processed successfully!',
                'data': {
                    'order_id': order_id,
                    'order_reference': order_ref,
                    'cafe_name': 'CaféNest Artisan Roastery',
                    'order_type': order_type,
                    'table_id': table_id,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'customer_email': customer_email,
                    'subtotal': computed_subtotal,
                    'tax_amount': tax_amount,
                    'discount_amount': discount_amount,
                    'total_amount': total_amount,
                    'status': initial_status,
                    'payment': {
                        'payment_id': payment_id,
                        'method': payment_method,
                        'transaction_ref': tx_ref,
                        'status': pay_status,
                        'is_simulated': True
                    },
                    'items': order_line_items
                }
            }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Order transaction failed: {str(e)}'}), 500
    finally:
        conn.close()

@orders_bp.route('/history', methods=['GET'])
@orders_bp.route('/my-orders', methods=['GET'])
def get_customer_order_history():
    """
    Returns order history strictly for the currently authenticated customer.
    Prevents IDOR by locking query to session['user_id'].
    """
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type != 'customer':
        return jsonify({
            'success': False,
            'message': 'Authentication required. Please sign in as a customer to view order history.'
        }), 401

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.order_id, o.order_reference, o.cafe_name, o.customer_id,
                       o.customer_name, o.customer_phone, o.customer_email,
                       o.table_id, o.order_type, o.status,
                       o.subtotal, o.tax_amount, o.discount_amount, o.total_amount,
                       o.special_instructions, o.created_at, o.updated_at,
                       t.table_number, t.location_area,
                       p.payment_id, p.method as payment_method, p.status as payment_status,
                       p.transaction_ref, p.is_simulated, p.paid_at
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                LEFT JOIN (
                    SELECT p1.*
                    FROM payments p1
                    INNER JOIN (
                        SELECT order_id, MAX(payment_id) as max_pay_id
                        FROM payments GROUP BY order_id
                    ) p2 ON p1.payment_id = p2.max_pay_id
                ) p ON o.order_id = p.order_id
                WHERE o.customer_id = %s
                ORDER BY o.created_at DESC;
            """, (user_id,))
            orders = cur.fetchall()

            order_ids = [o['order_id'] for o in orders]
            items_by_order = {}
            if order_ids:
                format_strings = ','.join(['%s'] * len(order_ids))
                cur.execute(f"""
                    SELECT od.order_id, od.menu_id, COALESCE(od.item_name, m.name) as item_name,
                           od.quantity, od.unit_price, od.subtotal, m.image_url, m.is_veg
                    FROM order_details od
                    LEFT JOIN menu m ON od.menu_id = m.menu_id
                    WHERE od.order_id IN ({format_strings})
                    ORDER BY od.order_detail_id ASC;
                """, order_ids)
                for item in cur.fetchall():
                    item['unit_price'] = float(item['unit_price'])
                    item['subtotal'] = float(item['subtotal'])
                    item['is_veg'] = bool(item['is_veg']) if item['is_veg'] is not None else True
                    items_by_order.setdefault(item['order_id'], []).append(item)

            for ord_row in orders:
                ord_row['subtotal'] = float(ord_row['subtotal'])
                ord_row['tax_amount'] = float(ord_row['tax_amount'])
                ord_row['discount_amount'] = float(ord_row['discount_amount'])
                ord_row['total_amount'] = float(ord_row['total_amount'])
                ord_row['created_at'] = ord_row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if ord_row['created_at'] else ''
                ord_row['updated_at'] = ord_row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if ord_row['updated_at'] else ''
                ord_row['paid_at'] = ord_row['paid_at'].strftime('%Y-%m-%d %H:%M:%S') if ord_row.get('paid_at') else ''
                ord_row['items'] = items_by_order.get(ord_row['order_id'], [])

            return jsonify({
                'success': True,
                'count': len(orders),
                'data': orders
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching order history: {str(e)}'}), 500
    finally:
        conn.close()

@orders_bp.route('', methods=['GET'])
def list_orders():
    """
    Searchable and filterable orders listing:
    - If caller is staff: can search & filter all orders.
    - If caller is customer: locked to their own customer_id.
    - If guest with ?ref= parameter: lookup that single reference.
    """
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    payment_method_filter = request.args.get('payment_method', '').strip()
    payment_status_filter = request.args.get('payment_status', '').strip()
    date_filter = request.args.get('date', '').strip()
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT o.order_id, o.order_reference, o.cafe_name, o.customer_id, o.customer_name,
                       o.customer_phone, o.customer_email, o.table_id,
                       o.order_type, o.status, o.subtotal, o.tax_amount, o.discount_amount, o.total_amount,
                       o.special_instructions, o.created_at,
                       t.table_number, t.location_area,
                       COALESCE(o.customer_name, c.name) as display_customer_name,
                       COALESCE(o.customer_phone, c.phone) as display_customer_phone,
                       p.method as payment_method, p.status as payment_status,
                       p.transaction_ref, p.is_simulated
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                LEFT JOIN (
                    SELECT p1.*
                    FROM payments p1
                    INNER JOIN (
                        SELECT order_id, MAX(payment_id) as max_pay_id
                        FROM payments GROUP BY order_id
                    ) p2 ON p1.payment_id = p2.max_pay_id
                ) p ON o.order_id = p.order_id
                WHERE 1=1
            """
            params = []

            # Role-based scoping (Customer ownership check)
            if user_type == 'customer':
                sql += " AND (o.customer_id = %s OR o.customer_email = %s)"
                params.extend([user_id, session.get('user_email', '')])
            elif user_type != 'staff':
                guest_ref = request.args.get('ref')
                if guest_ref:
                    sql += " AND o.order_reference = %s"
                    params.append(guest_ref)
                else:
                    return jsonify({'success': True, 'count': 0, 'data': []})

            # Search filters (for staff or customer search)
            if search_query:
                sql += """ AND (
                    o.order_reference LIKE %s OR 
                    o.customer_name LIKE %s OR 
                    o.customer_phone LIKE %s OR 
                    o.customer_email LIKE %s OR
                    t.table_number LIKE %s
                )"""
                term = f"%{search_query}%"
                params.extend([term, term, term, term, term])

            if status_filter and status_filter in VALID_STATUSES:
                sql += " AND o.status = %s"
                params.append(status_filter)

            if payment_method_filter:
                sql += " AND p.method = %s"
                params.append(payment_method_filter)

            if payment_status_filter:
                sql += " AND p.status = %s"
                params.append(payment_status_filter)

            if date_filter:
                sql += " AND DATE(o.created_at) = %s"
                params.append(date_filter)

            sql += " ORDER BY o.created_at DESC LIMIT %s OFFSET %s;"
            params.extend([limit, offset])

            cur.execute(sql, params)
            orders = cur.fetchall()

            for ord_row in orders:
                ord_row['subtotal'] = float(ord_row['subtotal'])
                ord_row['tax_amount'] = float(ord_row['tax_amount'])
                ord_row['discount_amount'] = float(ord_row['discount_amount'])
                ord_row['total_amount'] = float(ord_row['total_amount'])
                ord_row['created_at'] = ord_row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if ord_row['created_at'] else ''

            return jsonify({'success': True, 'count': len(orders), 'data': orders})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching orders: {str(e)}'}), 500
    finally:
        conn.close()

@orders_bp.route('/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    """
    Returns order details with strict authorization & IDOR protection:
    - Customer can only view their own order.
    - Staff can view any order.
    - Unauthenticated callers are rejected with 401.
    """
    user_type = session.get('user_type')
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'message': 'Authentication required to view order details.'}), 401

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.order_id, o.order_reference, o.cafe_name, o.customer_id, o.customer_name,
                       o.customer_phone, o.customer_email, o.table_id,
                       o.order_type, o.status, o.subtotal, o.tax_amount, o.discount_amount, o.total_amount,
                       o.special_instructions, o.created_at, o.updated_at,
                       t.table_number, t.location_area,
                       COALESCE(o.customer_name, c.name) as display_name,
                       COALESCE(o.customer_email, c.email) as display_email,
                       COALESCE(o.customer_phone, c.phone) as display_phone
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_id = %s;
            """, (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': 'Order not found.'}), 404

            # Strict IDOR check: Customer can only view their own order
            if user_type == 'customer' and order['customer_id'] != user_id:
                return jsonify({'success': False, 'message': 'Forbidden: You do not have permission to view this order.'}), 403

            order['subtotal'] = float(order['subtotal'])
            order['tax_amount'] = float(order['tax_amount'])
            order['discount_amount'] = float(order['discount_amount'])
            order['total_amount'] = float(order['total_amount'])
            order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M:%S') if order['created_at'] else ''
            order['updated_at'] = order['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if order['updated_at'] else ''

            # Fetch line items with snapshot name
            cur.execute("""
                SELECT od.order_detail_id, od.menu_id, COALESCE(od.item_name, m.name) as item_name,
                       od.quantity, od.unit_price, od.subtotal, m.image_url, m.is_veg
                FROM order_details od
                LEFT JOIN menu m ON od.menu_id = m.menu_id
                WHERE od.order_id = %s
                ORDER BY od.order_detail_id ASC;
            """, (order_id,))
            items = cur.fetchall()
            for it in items:
                it['unit_price'] = float(it['unit_price'])
                it['subtotal'] = float(it['subtotal'])
                it['is_veg'] = bool(it['is_veg']) if it['is_veg'] is not None else True
            order['items'] = items

            # Fetch payment record
            cur.execute("""
                SELECT payment_id, amount, method, status, transaction_ref, is_simulated, paid_at
                FROM payments WHERE order_id = %s ORDER BY payment_id DESC LIMIT 1;
            """, (order_id,))
            payment = cur.fetchone()
            if payment:
                payment['amount'] = float(payment['amount'])
                payment['paid_at'] = payment['paid_at'].strftime('%Y-%m-%d %H:%M:%S') if payment['paid_at'] else ''
            order['payment'] = payment

            # Fetch status transition history
            cur.execute("""
                SELECT osh.history_id, osh.previous_status, osh.new_status, osh.notes, osh.created_at,
                       s.name as changed_by_name, s.role as changed_by_role
                FROM order_status_history osh
                LEFT JOIN staff s ON osh.changed_by_staff_id = s.staff_id
                WHERE osh.order_id = %s
                ORDER BY osh.history_id ASC;
            """, (order_id,))
            history = cur.fetchall()
            for h in history:
                h['created_at'] = h['created_at'].strftime('%Y-%m-%d %H:%M:%S') if h['created_at'] else ''
            order['status_history'] = history

            return jsonify({'success': True, 'data': order})
    finally:
        conn.close()

@orders_bp.route('/track/<reference>', methods=['GET'])
def track_order_by_ref(reference):
    """
    Public and customer tracking by reference code e.g. NEST-XXXX.
    Enforces IDOR protection: if logged in as a customer, cannot track another customer's order.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT o.order_id, o.order_reference, o.cafe_name, o.order_type, o.status,
                       o.customer_id, o.customer_name, o.customer_phone, o.special_instructions,
                       o.subtotal, o.tax_amount, o.discount_amount, o.total_amount, o.created_at,
                       t.table_number, t.location_area
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                WHERE o.order_reference = %s;
            """, (reference.strip(),))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': f"Order reference '{reference}' not found."}), 404

            # IDOR check: If caller is a logged in customer, they cannot view an order belonging to another customer
            user_type = session.get('user_type')
            user_id = session.get('user_id')
            if user_type == 'customer' and order['customer_id'] and order['customer_id'] != user_id:
                return jsonify({'success': False, 'message': 'Forbidden: You do not have permission to access this order.'}), 403

            order['subtotal'] = float(order['subtotal'])
            order['tax_amount'] = float(order['tax_amount'])
            order['discount_amount'] = float(order['discount_amount'])
            order['total_amount'] = float(order['total_amount'])
            order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M:%S') if order['created_at'] else ''

            # Fetch line items
            cur.execute("""
                SELECT od.quantity, od.unit_price, od.subtotal,
                       COALESCE(od.item_name, m.name) as item_name, m.image_url, m.is_veg
                FROM order_details od
                LEFT JOIN menu m ON od.menu_id = m.menu_id
                WHERE od.order_id = %s
                ORDER BY od.order_detail_id ASC;
            """, (order['order_id'],))
            items = cur.fetchall()
            for it in items:
                it['unit_price'] = float(it['unit_price'])
                it['subtotal'] = float(it['subtotal'])
                it['is_veg'] = bool(it['is_veg']) if it['is_veg'] is not None else True
            order['items'] = items

            # Payment
            cur.execute("""
                SELECT payment_id, method, status, transaction_ref, amount, is_simulated, paid_at
                FROM payments WHERE order_id = %s ORDER BY payment_id DESC LIMIT 1;
            """, (order['order_id'],))
            payment = cur.fetchone()
            if payment:
                payment['amount'] = float(payment['amount'])
                payment['paid_at'] = payment['paid_at'].strftime('%Y-%m-%d %H:%M:%S') if payment['paid_at'] else ''
            order['payment'] = payment

            # Status history
            cur.execute("""
                SELECT osh.previous_status, osh.new_status, osh.notes, osh.created_at
                FROM order_status_history osh
                WHERE osh.order_id = %s
                ORDER BY osh.history_id ASC;
            """, (order['order_id'],))
            history = cur.fetchall()
            for h in history:
                h['created_at'] = h['created_at'].strftime('%Y-%m-%d %H:%M:%S') if h['created_at'] else ''
            order['status_history'] = history

            return jsonify({'success': True, 'data': order})
    finally:
        conn.close()

@orders_bp.route('/<int:order_id>/status', methods=['POST'])
@orders_bp.route('/update-status', methods=['POST'])
@staff_required
def update_order_status(order_id=None):
    """
    Staff-only endpoint to transition order status.
    Enforces valid state machine transitions:
    - Pending -> Confirmed, Cancelled
    - Confirmed -> Preparing, Cancelled
    - Preparing -> Ready, Cancelled
    - Ready -> Completed, Cancelled
    - Completed -> Terminal
    - Cancelled -> Terminal
    Rejects invalid transitions and logs changes to order_status_history.
    """
    data = request.get_json() or {}
    if order_id is None:
        order_id = data.get('order_id')
    new_status = data.get('status')
    notes = data.get('notes', '').strip() or None

    if not order_id or not new_status:
        return jsonify({'success': False, 'message': 'order_id and status are required.'}), 400

    if new_status not in VALID_STATUSES:
        return jsonify({'success': False, 'message': f"Invalid status. Allowed values: {', '.join(VALID_STATUSES)}"}), 400

    staff_id = session.get('user_id')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT order_id, order_reference, table_id, status FROM orders WHERE order_id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': 'Order not found.'}), 404

            current_status = order['status']

            # Enforce state transition rules
            allowed_next = VALID_TRANSITIONS.get(current_status, [])
            if new_status not in allowed_next:
                return jsonify({
                    'success': False,
                    'message': f"Invalid status transition from '{current_status}' to '{new_status}'. Allowed transitions: {', '.join(allowed_next) if allowed_next else 'None (Terminal state)'}."
                }), 400

            # Update orders table
            cur.execute("UPDATE orders SET status = %s WHERE order_id = %s;", (new_status, order_id))

            # Record in order_status_history audit log
            cur.execute("""
                INSERT INTO order_status_history (order_id, previous_status, new_status, changed_by_staff_id, notes)
                VALUES (%s, %s, %s, %s, %s);
            """, (order_id, current_status, new_status, staff_id, notes or f"Status advanced by staff to {new_status}"))

            # If order reached Completed or Cancelled, free up the table
            if new_status in ('Completed', 'Cancelled') and order['table_id']:
                cur.execute("UPDATE cafe_tables SET status = 'Available' WHERE table_id = %s;", (order['table_id'],))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Order #{order['order_reference']} status updated from '{current_status}' to '{new_status}'.",
                'data': {
                    'order_id': order_id,
                    'order_reference': order['order_reference'],
                    'previous_status': current_status,
                    'status': new_status
                }
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Status update failed: {str(e)}'}), 500
    finally:
        conn.close()

@orders_bp.route('/<int:order_id>/history', methods=['GET'])
def get_order_status_history_trail(order_id):
    """Returns the full status audit trail for a given order."""
    user_type = session.get('user_type')
    user_id = session.get('user_id')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT order_id, customer_id FROM orders WHERE order_id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                return jsonify({'success': False, 'message': 'Order not found.'}), 404

            if user_type == 'customer' and order['customer_id'] != user_id:
                return jsonify({'success': False, 'message': 'Forbidden.'}), 403

            cur.execute("""
                SELECT osh.history_id, osh.previous_status, osh.new_status, osh.notes, osh.created_at,
                       s.name as staff_name, s.role as staff_role
                FROM order_status_history osh
                LEFT JOIN staff s ON osh.changed_by_staff_id = s.staff_id
                WHERE osh.order_id = %s
                ORDER BY osh.history_id ASC;
            """, (order_id,))
            trail = cur.fetchall()
            for r in trail:
                r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else ''

            return jsonify({'success': True, 'data': trail})
    finally:
        conn.close()
