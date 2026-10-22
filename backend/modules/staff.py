from flask import Blueprint, request, jsonify
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import admin_required, hash_password

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('', methods=['GET'])
@admin_required
def get_staff():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT staff_id, name, email, phone, role, is_active, created_at
                FROM staff ORDER BY role ASC, name ASC;
            """)
            staff_list = cur.fetchall()
            for s in staff_list:
                s['is_active'] = bool(s['is_active'])
                s['created_at'] = s['created_at'].strftime('%Y-%m-%d') if s['created_at'] else ''
            return jsonify({'success': True, 'count': len(staff_list), 'data': staff_list})
    finally:
        conn.close()

@staff_bp.route('', methods=['POST'])
@admin_required
def add_staff():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    phone = data.get('phone', '').strip()
    role = data.get('role', 'Barista')

    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'Name, email, and password required.'}), 400

    if role not in ('Admin', 'Cashier', 'Barista', 'Waitstaff'):
        return jsonify({'success': False, 'message': 'Invalid role.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id FROM staff WHERE email = %s;", (email,))
            if cur.fetchone():
                return jsonify({'success': False, 'message': 'Email already registered for staff.'}), 400

            pwd_hash = hash_password(password)
            cur.execute("""
                INSERT INTO staff (name, email, password_hash, phone, role, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE);
            """, (name, email, pwd_hash, phone, role))
            new_id = cur.lastrowid
            conn.commit()
            return jsonify({'success': True, 'message': f"Staff member '{name}' ({role}) added successfully.", 'data': {'staff_id': new_id}}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@staff_bp.route('/toggle', methods=['POST'])
@admin_required
def toggle_staff_active():
    data = request.get_json() or {}
    staff_id = data.get('staff_id')
    if not staff_id:
        return jsonify({'success': False, 'message': 'staff_id is required.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_active, name FROM staff WHERE staff_id = %s;", (staff_id,))
            member = cur.fetchone()
            if not member:
                return jsonify({'success': False, 'message': 'Staff member not found.'}), 404

            new_status = not bool(member['is_active'])
            cur.execute("UPDATE staff SET is_active = %s WHERE staff_id = %s;", (new_status, staff_id))
            conn.commit()
            return jsonify({'success': True, 'message': f"Account for '{member['name']}' set to {'Active' if new_status else 'Inactive'}."})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()
