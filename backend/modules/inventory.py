from flask import Blueprint, request, jsonify, session
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('', methods=['GET'])
@staff_required
def get_inventory():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT i.inventory_id, i.supplier_id, i.item_name, i.quantity, i.unit,
                       i.reorder_level, i.cost_per_unit, i.updated_at,
                       s.supplier_name, s.contact_name, s.phone as supplier_phone,
                       CASE WHEN i.quantity <= i.reorder_level THEN TRUE ELSE FALSE END as is_low_stock
                FROM inventory i
                LEFT JOIN suppliers s ON i.supplier_id = s.supplier_id
                ORDER BY is_low_stock DESC, i.item_name ASC;
            """)
            items = cur.fetchall()
            for it in items:
                it['quantity'] = float(it['quantity'])
                it['reorder_level'] = float(it['reorder_level'])
                it['cost_per_unit'] = float(it['cost_per_unit'])
                it['is_low_stock'] = bool(it['is_low_stock'])
                it['updated_at'] = it['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if it['updated_at'] else ''

            return jsonify({'success': True, 'count': len(items), 'data': items})
    finally:
        conn.close()

@inventory_bp.route('/movements', methods=['GET'])
@staff_required
def get_movements():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sm.movement_id, sm.inventory_id, sm.quantity_change, sm.reason,
                       sm.notes, sm.created_at,
                       i.item_name, i.unit,
                       st.name as staff_name
                FROM stock_movements sm
                JOIN inventory i ON sm.inventory_id = i.inventory_id
                LEFT JOIN staff st ON sm.staff_id = st.staff_id
                ORDER BY sm.created_at DESC LIMIT 50;
            """)
            movements = cur.fetchall()
            for m in movements:
                m['quantity_change'] = float(m['quantity_change'])
                m['created_at'] = m['created_at'].strftime('%Y-%m-%d %H:%M:%S') if m['created_at'] else ''
            return jsonify({'success': True, 'data': movements})
    finally:
        conn.close()

@inventory_bp.route('/movement', methods=['POST'])
@staff_required
def record_stock_movement():
    data = request.get_json() or {}
    inventory_id = data.get('inventory_id')
    quantity_change = data.get('quantity_change')
    reason = data.get('reason')
    notes = data.get('notes', '').strip()
    staff_id = session.get('user_id')

    valid_reasons = ['Restock', 'Waste / Spoilage', 'Daily Prep Usage', 'Inventory Audit Adjustment', 'Returned']

    if not inventory_id or quantity_change is None or reason not in valid_reasons:
        return jsonify({'success': False, 'message': 'Valid inventory_id, quantity_change, and approved reason required.'}), 400

    try:
        qty_change = float(quantity_change)
    except ValueError:
        return jsonify({'success': False, 'message': 'quantity_change must be a valid number.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check current inventory
            cur.execute("SELECT quantity, item_name FROM inventory WHERE inventory_id = %s;", (inventory_id,))
            inv_item = cur.fetchone()
            if not inv_item:
                return jsonify({'success': False, 'message': 'Stock item not found.'}), 404

            current_qty = float(inv_item['quantity'])
            new_qty = current_qty + qty_change

            if new_qty < 0:
                return jsonify({'success': False, 'message': f"Cannot deduct {abs(qty_change)}. Available stock is only {current_qty}."}), 400

            # Atomic transaction: insert movement + update inventory
            cur.execute("""
                INSERT INTO stock_movements (inventory_id, quantity_change, reason, notes, staff_id)
                VALUES (%s, %s, %s, %s, %s);
            """, (inventory_id, qty_change, reason, notes, staff_id))

            cur.execute("""
                UPDATE inventory SET quantity = %s WHERE inventory_id = %s;
            """, (new_qty, inventory_id))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f"Recorded stock movement for '{inv_item['item_name']}'. New stock balance: {new_qty}",
                'data': {'inventory_id': inventory_id, 'new_quantity': new_qty}
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@inventory_bp.route('/suppliers', methods=['GET'])
@staff_required
def list_suppliers():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.supplier_id, s.supplier_name, s.contact_name, s.phone,
                       s.email, s.address, s.supplied_items, s.is_active,
                       COUNT(i.inventory_id) as linked_items
                FROM suppliers s
                LEFT JOIN inventory i ON s.supplier_id = i.supplier_id
                GROUP BY s.supplier_id
                ORDER BY s.supplier_name ASC;
            """)
            suppliers = cur.fetchall()
            return jsonify({'success': True, 'data': suppliers})
    finally:
        conn.close()

@inventory_bp.route('/suppliers', methods=['POST'])
@staff_required
def add_supplier():
    data = request.get_json() or {}
    name = data.get('supplier_name', '').strip()
    contact = data.get('contact_name', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    address = data.get('address', '').strip()
    supplied = data.get('supplied_items', '').strip()

    if not name:
        return jsonify({'success': False, 'message': 'Supplier name is required.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO suppliers (supplier_name, contact_name, phone, email, address, supplied_items)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (name, contact, phone, email, address, supplied))
            conn.commit()
            return jsonify({'success': True, 'message': f"Supplier '{name}' added successfully."}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()
