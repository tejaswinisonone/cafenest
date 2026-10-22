from flask import Blueprint, request, jsonify
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

tables_bp = Blueprint('tables', __name__)

@tables_bp.route('', methods=['GET'])
def list_tables():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.table_id, t.table_number, t.seating_capacity, t.location_area, t.status,
                       o.order_id as active_order_id, o.order_reference as active_order_ref, o.status as active_order_status
                FROM cafe_tables t
                LEFT JOIN orders o ON t.table_id = o.table_id AND o.status IN ('Pending', 'Confirmed', 'Preparing', 'Ready')
                ORDER BY t.table_id ASC;
            """)
            tables = cur.fetchall()
            return jsonify({'success': True, 'count': len(tables), 'data': tables})
    finally:
        conn.close()

@tables_bp.route('/status', methods=['POST'])
@staff_required
def update_table_status():
    data = request.get_json() or {}
    table_id = data.get('table_id')
    status = data.get('status')

    if not table_id or status not in ('Available', 'Occupied', 'Reserved'):
        return jsonify({'success': False, 'message': 'Valid table_id and status (Available, Occupied, Reserved) required.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cafe_tables SET status = %s WHERE table_id = %s;", (status, table_id))
            conn.commit()
            return jsonify({'success': True, 'message': f'Table status updated to {status}.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()
