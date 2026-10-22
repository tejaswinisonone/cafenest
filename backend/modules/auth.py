from flask import Blueprint, request, jsonify, session
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import hash_password, verify_password, customer_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    phone = data.get('phone', '').strip()

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'Name, email, and password are required.'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check for existing email in customers or staff
            cur.execute("SELECT customer_id FROM customers WHERE email = %s;", (email,))
            if cur.fetchone():
                return jsonify({'success': False, 'message': 'Email already registered. Please sign in.'}), 400

            pwd_hash = hash_password(password)
            cur.execute("""
                INSERT INTO customers (name, email, password_hash, phone, loyalty_points)
                VALUES (%s, %s, %s, %s, 50);
            """, (name, email, pwd_hash, phone))
            customer_id = cur.lastrowid
            conn.commit()

            # Automatically establish customer session
            session['user_id'] = customer_id
            session['user_type'] = 'customer'
            session['user_name'] = name
            session['user_email'] = email

            return jsonify({
                'success': True,
                'message': 'Registration successful! Welcome to CaféNest.',
                'data': {
                    'user_id': customer_id,
                    'name': name,
                    'email': email,
                    'user_type': 'customer',
                    'loyalty_points': 50
                }
            }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Registration failed: {str(e)}'}), 500
    finally:
        conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    login_type = data.get('login_type', 'all')  # 'customer', 'staff', or 'all'

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check staff first if login_type allows
            if login_type in ('staff', 'all'):
                cur.execute("""
                    SELECT staff_id, name, email, password_hash, role, is_active
                    FROM staff WHERE email = %s;
                """, (email,))
                staff_user = cur.fetchone()
                if staff_user and verify_password(password, staff_user['password_hash']):
                    if not staff_user['is_active']:
                        return jsonify({'success': False, 'message': 'This staff account has been deactivated.'}), 403

                    session['user_id'] = staff_user['staff_id']
                    session['user_type'] = 'staff'
                    session['user_role'] = staff_user['role']
                    session['user_name'] = staff_user['name']
                    session['user_email'] = staff_user['email']

                    return jsonify({
                        'success': True,
                        'message': f"Welcome back, {staff_user['name']}!",
                        'data': {
                            'user_id': staff_user['staff_id'],
                            'name': staff_user['name'],
                            'email': staff_user['email'],
                            'user_type': 'staff',
                            'role': staff_user['role']
                        }
                    })

            # Check customers
            if login_type in ('customer', 'all'):
                cur.execute("""
                    SELECT customer_id, name, email, password_hash, phone, loyalty_points
                    FROM customers WHERE email = %s;
                """, (email,))
                customer = cur.fetchone()
                if customer and verify_password(password, customer['password_hash']):
                    session['user_id'] = customer['customer_id']
                    session['user_type'] = 'customer'
                    session['user_name'] = customer['name']
                    session['user_email'] = customer['email']

                    return jsonify({
                        'success': True,
                        'message': f"Welcome back, {customer['name']}!",
                        'data': {
                            'user_id': customer['customer_id'],
                            'name': customer['name'],
                            'email': customer['email'],
                            'user_type': 'customer',
                            'phone': customer['phone'],
                            'loyalty_points': customer['loyalty_points']
                        }
                    })

            return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login error: {str(e)}'}), 500
    finally:
        conn.close()

@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or not user_type:
        return jsonify({'success': True, 'data': None, 'authenticated': False})

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if user_type == 'staff':
                cur.execute("SELECT staff_id, name, email, phone, role, is_active FROM staff WHERE staff_id = %s;", (user_id,))
                user = cur.fetchone()
                if user:
                    user['user_type'] = 'staff'
                    return jsonify({'success': True, 'authenticated': True, 'data': user})
            else:
                cur.execute("SELECT customer_id, name, email, phone, address, loyalty_points FROM customers WHERE customer_id = %s;", (user_id,))
                user = cur.fetchone()
                if user:
                    user['user_type'] = 'customer'
                    # Also fetch order count
                    cur.execute("SELECT COUNT(*) as total_orders FROM orders WHERE customer_id = %s;", (user_id,))
                    count_res = cur.fetchone()
                    user['total_orders'] = count_res['total_orders'] if count_res else 0
                    return jsonify({'success': True, 'authenticated': True, 'data': user})

            session.clear()
            return jsonify({'success': True, 'authenticated': False, 'data': None})
    finally:
        conn.close()

@auth_bp.route('/profile', methods=['PUT'])
@customer_required
def update_profile():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if user_type != 'customer':
        return jsonify({'success': False, 'message': 'Only customers can update profile here.'}), 403

    if not name:
        return jsonify({'success': False, 'message': 'Name cannot be empty.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE customers
                SET name = %s, phone = %s, address = %s
                WHERE customer_id = %s;
            """, (name, phone, address, user_id))
            conn.commit()
            session['user_name'] = name
            return jsonify({'success': True, 'message': 'Profile updated successfully!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Update failed: {str(e)}'}), 500
    finally:
        conn.close()
