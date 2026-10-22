import hashlib
from functools import wraps
from flask import session, jsonify, request

def hash_password(password: str) -> str:
    """Hashes a password string using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against stored hash."""
    return hash_password(plain_password) == hashed_password

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_type = session.get('user_type')
        if not session.get('user_id') or user_type not in ('customer', 'staff', 'admin'):
            return jsonify({
                'success': False,
                'message': 'Authentication required. Please log in to proceed.'
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_type = session.get('user_type')
        if not session.get('user_id') or user_type not in ('staff', 'admin'):
            return jsonify({
                'success': False,
                'message': 'Unauthorized. Staff privileges required.'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_type = session.get('user_type')
        user_role = session.get('user_role')
        if not session.get('user_id') or user_type != 'staff' or user_role != 'Admin':
            return jsonify({
                'success': False,
                'message': 'Access forbidden. Administrator privileges required.'
            }), 403
        return f(*args, **kwargs)
    return decorated_function
