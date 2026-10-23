from flask import Blueprint, request, jsonify
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

tables_bp = Blueprint('tables', __name__)

VALID_TABLE_STATUSES = ('Available', 'Occupied', 'Reserved')

@tables_bp.route('', methods=['GET'])
def list_tables():
    """
    Returns list of cafe tables.
    Optional query params:
    - status: 'Available', 'Occupied', or 'Reserved'
    - min_capacity: integer (party size)
    """
    status_filter = request.args.get('status')
    min_capacity = request.args.get('min_capacity')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT t.table_id, t.table_number, t.cafe_name, t.seating_capacity,
                       t.location_area, t.status, t.created_at, t.updated_at,
                       o.order_id as active_order_id, o.order_reference as active_order_ref,
                       o.status as active_order_status, o.customer_name as active_customer_name
                FROM cafe_tables t
                LEFT JOIN orders o ON t.table_id = o.table_id AND o.status IN ('Pending', 'Confirmed', 'Preparing', 'Ready')
                WHERE 1=1
            """
            params = []

            if status_filter and status_filter in VALID_TABLE_STATUSES:
                sql += " AND t.status = %s"
                params.append(status_filter)

            if min_capacity:
                try:
                    min_cap = int(min_capacity)
                    sql += " AND t.seating_capacity >= %s"
                    params.append(min_cap)
                except ValueError:
                    pass

            sql += " ORDER BY t.table_id ASC;"
            cur.execute(sql, params)
            tables = cur.fetchall()

            for t in tables:
                t['created_at'] = t['created_at'].strftime('%Y-%m-%d %H:%M:%S') if t.get('created_at') else ''
                t['updated_at'] = t['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if t.get('updated_at') else ''

            return jsonify({
                'success': True,
                'count': len(tables),
                'data': tables
            }), 200
    finally:
        conn.close()

@tables_bp.route('/<int:table_id>', methods=['GET'])
def get_table_details(table_id):
    """Returns details for a single table."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.table_id, t.table_number, t.cafe_name, t.seating_capacity,
                       t.location_area, t.status, t.created_at, t.updated_at,
                       o.order_id as active_order_id, o.order_reference as active_order_ref,
                       o.status as active_order_status
                FROM cafe_tables t
                LEFT JOIN orders o ON t.table_id = o.table_id AND o.status IN ('Pending', 'Confirmed', 'Preparing', 'Ready')
                WHERE t.table_id = %s;
            """, (table_id,))
            table = cur.fetchone()
            if not table:
                return jsonify({'success': False, 'message': f'Table ID {table_id} not found.'}), 404

            table['created_at'] = table['created_at'].strftime('%Y-%m-%d %H:%M:%S') if table.get('created_at') else ''
            table['updated_at'] = table['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if table.get('updated_at') else ''

            return jsonify({'success': True, 'data': table}), 200
    finally:
        conn.close()

@tables_bp.route('', methods=['POST'])
@staff_required
def create_table():
    """
    Staff-only endpoint to add a new cafe table.
    Enforces:
    - Valid table_number (unique within cafe)
    - Valid seating_capacity (integer > 0)
    - Valid status
    """
    data = request.get_json() or {}
    table_number = str(data.get('table_number', '')).strip()
    seating_capacity = data.get('seating_capacity')
    location_area = str(data.get('location_area', 'Main Dining Hall')).strip()
    status = data.get('status', 'Available')
    cafe_name = str(data.get('cafe_name', 'CaféNest Artisan Roastery')).strip()

    if not table_number:
        return jsonify({'success': False, 'message': 'table_number is required.'}), 400

    if seating_capacity is None:
        return jsonify({'success': False, 'message': 'seating_capacity is required.'}), 400

    try:
        seating_capacity = int(seating_capacity)
        if seating_capacity <= 0:
            return jsonify({'success': False, 'message': 'seating_capacity must be a positive integer (> 0).'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'seating_capacity must be a valid integer.'}), 400

    if status not in VALID_TABLE_STATUSES:
        return jsonify({'success': False, 'message': f"Invalid status. Allowed: {', '.join(VALID_TABLE_STATUSES)}"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check duplicate table_number within cafe
            cur.execute("""
                SELECT table_id FROM cafe_tables
                WHERE table_number = %s AND cafe_name = %s;
            """, (table_number, cafe_name))
            if cur.fetchone():
                return jsonify({'success': False, 'message': f"Table '{table_number}' already exists in {cafe_name}."}), 400

            cur.execute("""
                INSERT INTO cafe_tables (table_number, cafe_name, seating_capacity, location_area, status)
                VALUES (%s, %s, %s, %s, %s);
            """, (table_number, cafe_name, seating_capacity, location_area, status))
            new_id = cur.lastrowid
            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Table '{table_number}' created successfully.",
                'data': {
                    'table_id': new_id,
                    'table_number': table_number,
                    'cafe_name': cafe_name,
                    'seating_capacity': seating_capacity,
                    'location_area': location_area,
                    'status': status
                }
            }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Failed to create table: {str(e)}'}), 500
    finally:
        conn.close()

@tables_bp.route('/<int:table_id>', methods=['PUT'])
@staff_required
def update_table(table_id):
    """
    Staff-only endpoint to edit table details.
    """
    data = request.get_json() or {}
    table_number = str(data.get('table_number', '')).strip()
    seating_capacity = data.get('seating_capacity')
    location_area = data.get('location_area')
    status = data.get('status')
    cafe_name = data.get('cafe_name')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cafe_tables WHERE table_id = %s;", (table_id,))
            table = cur.fetchone()
            if not table:
                return jsonify({'success': False, 'message': f'Table ID {table_id} not found.'}), 404

            target_number = table_number if table_number else table['table_number']
            target_cafe = cafe_name if cafe_name else table['cafe_name']

            # Check duplicate table_number
            cur.execute("""
                SELECT table_id FROM cafe_tables
                WHERE table_number = %s AND cafe_name = %s AND table_id != %s;
            """, (target_number, target_cafe, table_id))
            if cur.fetchone():
                return jsonify({'success': False, 'message': f"Table number '{target_number}' is already in use."}), 400

            target_capacity = table['seating_capacity']
            if seating_capacity is not None:
                try:
                    target_capacity = int(seating_capacity)
                    if target_capacity <= 0:
                        return jsonify({'success': False, 'message': 'seating_capacity must be a positive integer.'}), 400
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Invalid seating_capacity.'}), 400

            target_status = table['status']
            if status is not None:
                if status not in VALID_TABLE_STATUSES:
                    return jsonify({'success': False, 'message': f"Invalid status: {status}"}), 400
                target_status = status

            target_area = location_area if location_area is not None else table['location_area']

            cur.execute("""
                UPDATE cafe_tables
                SET table_number = %s, cafe_name = %s, seating_capacity = %s, location_area = %s, status = %s
                WHERE table_id = %s;
            """, (target_number, target_cafe, target_capacity, target_area, target_status, table_id))
            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Table '{target_number}' updated successfully.",
                'data': {
                    'table_id': table_id,
                    'table_number': target_number,
                    'cafe_name': target_cafe,
                    'seating_capacity': target_capacity,
                    'location_area': target_area,
                    'status': target_status
                }
            }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Update failed: {str(e)}'}), 500
    finally:
        conn.close()

@tables_bp.route('/<int:table_id>/status', methods=['PATCH', 'POST'])
@tables_bp.route('/status', methods=['POST'])
@staff_required
def update_table_status(table_id=None):
    """
    Staff-only endpoint to update table status: Available, Occupied, Reserved.
    """
    data = request.get_json() or {}
    if table_id is None:
        table_id = data.get('table_id')
    status = data.get('status')

    if not table_id:
        return jsonify({'success': False, 'message': 'table_id is required.'}), 400

    try:
        table_id = int(table_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid table_id format.'}), 400

    if not status or status not in VALID_TABLE_STATUSES:
        return jsonify({'success': False, 'message': f"Valid status required: {', '.join(VALID_TABLE_STATUSES)}"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT table_id, table_number, status FROM cafe_tables WHERE table_id = %s;", (table_id,))
            table = cur.fetchone()
            if not table:
                return jsonify({'success': False, 'message': 'Table not found.'}), 404

            cur.execute("UPDATE cafe_tables SET status = %s WHERE table_id = %s;", (status, table_id))
            conn.commit()
            return jsonify({
                'success': True,
                'message': f"Table '{table['table_number']}' status updated to {status}.",
                'data': {'table_id': table_id, 'status': status}
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@tables_bp.route('/<int:table_id>', methods=['DELETE'])
@staff_required
def delete_table(table_id):
    """
    Safely deletes a table only if it is not referenced by active or historical orders.
    Enforces referential integrity protection.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT table_id, table_number FROM cafe_tables WHERE table_id = %s;", (table_id,))
            table = cur.fetchone()
            if not table:
                return jsonify({'success': False, 'message': f'Table ID {table_id} not found.'}), 404

            # Safety Check: Does any order reference this table?
            cur.execute("SELECT COUNT(*) as order_count FROM orders WHERE table_id = %s;", (table_id,))
            ref_count = cur.fetchone()['order_count']
            if ref_count > 0:
                return jsonify({
                    'success': False,
                    'message': f"Cannot delete table: Table '{table['table_number']}' is referenced by {ref_count} active or historical order(s)."
                }), 400

            # Safe to delete
            cur.execute("DELETE FROM cafe_tables WHERE table_id = %s;", (table_id,))
            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Table '{table['table_number']}' was safely removed from the system."
            }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Table deletion failed: {str(e)}'}), 500
    finally:
        conn.close()
