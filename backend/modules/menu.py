from flask import Blueprint, request, jsonify, session
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

menu_bp = Blueprint('menu', __name__)

@menu_bp.route('', methods=['GET'])
def list_menu():
    category_id = request.args.get('category_id')
    query = request.args.get('q', '').strip()
    include_unavailable = request.args.get('include_unavailable', 'false').lower() == 'true'

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT m.menu_id, m.category_id, c.category_name, m.name, 
                       m.description, m.price, m.image_url, m.is_veg, 
                       m.is_available, m.created_at
                FROM menu m
                JOIN categories c ON m.category_id = c.category_id
                WHERE c.is_active = TRUE
            """
            params = []

            if not include_unavailable:
                sql += " AND m.is_available = TRUE"

            if category_id and category_id.isdigit():
                sql += " AND m.category_id = %s"
                params.append(int(category_id))

            if query:
                sql += " AND (m.name LIKE %s OR m.description LIKE %s OR c.category_name LIKE %s)"
                term = f"%{query}%"
                params.extend([term, term, term])

            sql += " ORDER BY c.display_order ASC, m.menu_id ASC;"
            cur.execute(sql, params)
            items = cur.fetchall()

            # Format prices to float for JSON
            for item in items:
                item['price'] = float(item['price'])
                item['is_veg'] = bool(item['is_veg'])
                item['is_available'] = bool(item['is_available'])

            return jsonify({
                'success': True,
                'count': len(items),
                'data': items
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching menu: {str(e)}'}), 500
    finally:
        conn.close()

@menu_bp.route('/categories', methods=['GET'])
def list_categories():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.category_id, c.category_name, c.description, c.display_order, c.is_active,
                       COUNT(m.menu_id) as total_items,
                       SUM(CASE WHEN m.is_available = TRUE THEN 1 ELSE 0 END) as active_items
                FROM categories c
                LEFT JOIN menu m ON c.category_id = m.category_id
                GROUP BY c.category_id
                ORDER BY c.display_order ASC, c.category_name ASC;
            """)
            categories = cur.fetchall()
            for cat in categories:
                cat['is_active'] = bool(cat['is_active'])
                cat['total_items'] = int(cat['total_items'] or 0)
                cat['active_items'] = int(cat['active_items'] or 0)

            return jsonify({
                'success': True,
                'data': categories
            })
    finally:
        conn.close()

@menu_bp.route('/save', methods=['POST'])
@staff_required
def save_menu_item():
    data = request.get_json() or {}
    menu_id = data.get('menu_id')
    category_id = data.get('category_id')
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    price = data.get('price')
    image_url = data.get('image_url', '').strip() or 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=600&q=80'
    is_veg = bool(data.get('is_veg', True))
    is_available = bool(data.get('is_available', True))
    staff_id = session.get('user_id')

    if not name or not category_id or price is None:
        return jsonify({'success': False, 'message': 'Item name, category, and price are required.'}), 400

    try:
        price = float(price)
        if price <= 0:
            return jsonify({'success': False, 'message': 'Price must be greater than zero.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid price format.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if menu_id:
                # Update existing item
                cur.execute("SELECT price FROM menu WHERE menu_id = %s;", (menu_id,))
                existing = cur.fetchone()
                if not existing:
                    return jsonify({'success': False, 'message': 'Menu item not found.'}), 404

                old_price = float(existing['price'])
                cur.execute("""
                    UPDATE menu
                    SET category_id = %s, name = %s, description = %s, price = %s,
                        image_url = %s, is_veg = %s, is_available = %s
                    WHERE menu_id = %s;
                """, (category_id, name, description, price, image_url, is_veg, is_available, menu_id))

                # Log price changes in menu_price_audit table per TRD requirement
                if abs(old_price - price) > 0.001:
                    cur.execute("""
                        INSERT INTO menu_price_audit (menu_id, old_price, new_price, changed_by_staff_id)
                        VALUES (%s, %s, %s, %s);
                    """, (menu_id, old_price, price, staff_id))

                conn.commit()
                return jsonify({'success': True, 'message': f"Menu item '{name}' updated successfully."})
            else:
                # Insert new item
                cur.execute("""
                    INSERT INTO menu (category_id, name, description, price, image_url, is_veg, is_available)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (category_id, name, description, price, image_url, is_veg, is_available))
                new_id = cur.lastrowid
                conn.commit()
                return jsonify({'success': True, 'message': f"Menu item '{name}' added successfully.", 'data': {'menu_id': new_id}}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error saving menu item: {str(e)}'}), 500
    finally:
        conn.close()

@menu_bp.route('/toggle-availability', methods=['POST'])
@staff_required
def toggle_availability():
    data = request.get_json() or {}
    menu_id = data.get('menu_id')
    if not menu_id:
        return jsonify({'success': False, 'message': 'menu_id is required.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_available, name FROM menu WHERE menu_id = %s;", (menu_id,))
            item = cur.fetchone()
            if not item:
                return jsonify({'success': False, 'message': 'Item not found.'}), 404

            new_status = not bool(item['is_available'])
            cur.execute("UPDATE menu SET is_available = %s WHERE menu_id = %s;", (new_status, menu_id))
            conn.commit()

            status_str = "Available" if new_status else "Unavailable (Sold Out)"
            return jsonify({
                'success': True,
                'message': f"'{item['name']}' is now marked as {status_str}.",
                'data': {'menu_id': menu_id, 'is_available': new_status}
            })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Update failed: {str(e)}'}), 500
    finally:
        conn.close()

@menu_bp.route('/categories/save', methods=['POST'])
@staff_required
def save_category():
    data = request.get_json() or {}
    category_id = data.get('category_id')
    name = data.get('category_name', '').strip()
    description = data.get('description', '').strip()
    display_order = int(data.get('display_order', 0))

    if not name:
        return jsonify({'success': False, 'message': 'Category name is required.'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if category_id:
                cur.execute("""
                    UPDATE categories
                    SET category_name = %s, description = %s, display_order = %s
                    WHERE category_id = %s;
                """, (name, description, display_order, category_id))
                conn.commit()
                return jsonify({'success': True, 'message': 'Category updated successfully.'})
            else:
                cur.execute("""
                    INSERT INTO categories (category_name, description, display_order)
                    VALUES (%s, %s, %s);
                """, (name, description, display_order))
                conn.commit()
                return jsonify({'success': True, 'message': 'Category created successfully.'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error saving category: {str(e)}'}), 500
    finally:
        conn.close()
