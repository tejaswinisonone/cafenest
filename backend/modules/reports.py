from datetime import datetime
from flask import Blueprint, request, jsonify
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

reports_bp = Blueprint('reports', __name__)

def validate_date_range(start_str, end_str):
    """
    Validates start_date and end_date strings in YYYY-MM-DD format.
    Returns (start_dt, end_dt, error_message).
    """
    start_dt, end_dt = None, None
    if start_str:
        try:
            start_dt = datetime.strptime(start_str.strip(), '%Y-%m-%d').date()
        except ValueError:
            return None, None, f"Invalid start_date '{start_str}'. Expected format YYYY-MM-DD."
    if end_str:
        try:
            end_dt = datetime.strptime(end_str.strip(), '%Y-%m-%d').date()
        except ValueError:
            return None, None, f"Invalid end_date '{end_str}'. Expected format YYYY-MM-DD."

    if start_dt and end_dt and start_dt > end_dt:
        return None, None, "start_date cannot be later than end_date."

    return start_dt, end_dt, None

@reports_bp.route('/dashboard', methods=['GET'])
@staff_required
def dashboard_metrics():
    """
    Returns real-time or freshly calculated administrator metrics from MySQL.
    Supports optional date filtering (start_date, end_date) with server-side validation.
    Excludes cancelled orders from sales and clearly distinguishes settled from pending sales.
    """
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date, date_err = validate_date_range(start_str, end_str)
    if date_err:
        return jsonify({'success': False, 'message': date_err}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Build date filter clause for orders
            date_sql = ""
            date_params = []
            if start_date and end_date:
                date_sql = " AND DATE(o.created_at) BETWEEN %s AND %s"
                date_params.extend([start_date, end_date])
            elif start_date:
                date_sql = " AND DATE(o.created_at) >= %s"
                date_params.append(start_date)
            elif end_date:
                date_sql = " AND DATE(o.created_at) <= %s"
                date_params.append(end_date)

            # 1. Total Orders & Status Counts
            cur.execute(f"""
                SELECT COUNT(*) as total_orders,
                       SUM(CASE WHEN o.status = 'Pending' THEN 1 ELSE 0 END) as pending_orders,
                       SUM(CASE WHEN o.status = 'Confirmed' THEN 1 ELSE 0 END) as confirmed_orders,
                       SUM(CASE WHEN o.status = 'Preparing' THEN 1 ELSE 0 END) as preparing_orders,
                       SUM(CASE WHEN o.status = 'Ready' THEN 1 ELSE 0 END) as ready_orders,
                       SUM(CASE WHEN o.status = 'Completed' THEN 1 ELSE 0 END) as completed_orders,
                       SUM(CASE WHEN o.status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled_orders
                FROM orders o
                WHERE 1=1 {date_sql};
            """, date_params)
            order_counts = cur.fetchone() or {}

            # 2. Sales Calculations: Total Sales (non-cancelled), Settled vs Pending payments
            cur.execute(f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN o.status != 'Cancelled' THEN o.total_amount ELSE 0 END), 0) as total_sales,
                    COALESCE(SUM(CASE WHEN o.status != 'Cancelled' AND p.status = 'Completed' THEN o.total_amount ELSE 0 END), 0) as settled_sales,
                    COALESCE(SUM(CASE WHEN o.status != 'Cancelled' AND (p.status = 'Pending' OR p.status IS NULL) THEN o.total_amount ELSE 0 END), 0) as pending_sales
                FROM orders o
                LEFT JOIN (
                    SELECT p1.order_id, p1.status
                    FROM payments p1
                    INNER JOIN (
                        SELECT order_id, MAX(payment_id) as max_p_id
                        FROM payments GROUP BY order_id
                    ) p2 ON p1.payment_id = p2.max_p_id
                ) p ON o.order_id = p.order_id
                WHERE 1=1 {date_sql};
            """, date_params)
            sales_data = cur.fetchone() or {}

            # 3. Tables Status Breakdown
            cur.execute("""
                SELECT COUNT(*) as total_tables,
                       COALESCE(SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END), 0) as occupied_tables,
                       COALESCE(SUM(CASE WHEN status = 'Reserved' THEN 1 ELSE 0 END), 0) as reserved_tables,
                       COALESCE(SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END), 0) as available_tables
                FROM cafe_tables;
            """)
            tables_data = cur.fetchone() or {}

            # 4. Low-stock inventory items (quantity <= reorder_level)
            cur.execute("""
                SELECT COUNT(*) as low_stock_count
                FROM inventory
                WHERE quantity <= reorder_level;
            """)
            low_stock_count = cur.fetchone()['low_stock_count']

            cur.execute("""
                SELECT i.inventory_id, i.item_name, i.quantity, i.unit, i.reorder_level,
                       s.supplier_name
                FROM inventory i
                LEFT JOIN suppliers s ON i.supplier_id = s.supplier_id
                WHERE i.quantity <= i.reorder_level
                ORDER BY i.quantity ASC
                LIMIT 10;
            """)
            low_stock_items = cur.fetchall()
            for it in low_stock_items:
                it['quantity'] = float(it['quantity'])
                it['reorder_level'] = float(it['reorder_level'])

            # 5. Recent orders (last 8 matching filter)
            cur.execute(f"""
                SELECT o.order_id, o.order_reference, o.cafe_name, o.order_type, o.status,
                       o.subtotal, o.tax_amount, o.discount_amount, o.total_amount, o.created_at,
                       t.table_number,
                       COALESCE(o.customer_name, c.name, 'Walk-in Patron') as customer_name,
                       p.method as payment_method, p.status as payment_status
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
                WHERE 1=1 {date_sql}
                ORDER BY o.created_at DESC
                LIMIT 8;
            """, date_params)
            recent_orders = cur.fetchall()
            for r in recent_orders:
                r['subtotal'] = float(r['subtotal'])
                r['tax_amount'] = float(r['tax_amount'])
                r['total_amount'] = float(r['total_amount'])
                r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M') if r.get('created_at') else ''

            # 6. Popular menu items ranked by quantity sold (from order_details for non-cancelled orders)
            cur.execute(f"""
                SELECT m.menu_id, m.name, c.category_name, m.price,
                       COALESCE(SUM(od.quantity), 0) as total_sold,
                       COALESCE(SUM(od.subtotal), 0) as total_revenue
                FROM menu m
                JOIN categories c ON m.category_id = c.category_id
                LEFT JOIN order_details od ON m.menu_id = od.menu_id
                LEFT JOIN orders o ON od.order_id = o.order_id AND o.status != 'Cancelled' {date_sql.replace('o.created_at', 'o.created_at')}
                GROUP BY m.menu_id, m.name, c.category_name, m.price
                ORDER BY total_sold DESC, total_revenue DESC
                LIMIT 8;
            """, date_params)
            popular_items = cur.fetchall()
            for p in popular_items:
                p['price'] = float(p['price'])
                p['total_sold'] = int(p['total_sold'])
                p['total_revenue'] = float(p['total_revenue'])

            return jsonify({
                'success': True,
                'data': {
                    'date_filter': {
                        'start_date': str(start_date) if start_date else None,
                        'end_date': str(end_date) if end_date else None
                    },
                    'summary': {
                        'total_orders': int(order_counts.get('total_orders') or 0),
                        'total_sales': float(sales_data.get('total_sales') or 0.0),
                        'settled_sales': float(sales_data.get('settled_sales') or 0.0),
                        'pending_sales': float(sales_data.get('pending_sales') or 0.0),
                        'pending_orders': int(order_counts.get('pending_orders') or 0),
                        'confirmed_orders': int(order_counts.get('confirmed_orders') or 0),
                        'preparing_orders': int(order_counts.get('preparing_orders') or 0),
                        'ready_orders': int(order_counts.get('ready_orders') or 0),
                        'completed_orders': int(order_counts.get('completed_orders') or 0),
                        'cancelled_orders': int(order_counts.get('cancelled_orders') or 0),
                        'active_orders': int(
                            (order_counts.get('pending_orders') or 0) +
                            (order_counts.get('confirmed_orders') or 0) +
                            (order_counts.get('preparing_orders') or 0) +
                            (order_counts.get('ready_orders') or 0)
                        ),
                        'low_stock_count': int(low_stock_count)
                    },
                    'tables': {
                        'total': int(tables_data.get('total_tables') or 0),
                        'occupied': int(tables_data.get('occupied_tables') or 0),
                        'reserved': int(tables_data.get('reserved_tables') or 0),
                        'available': int(tables_data.get('available_tables') or 0)
                    },
                    'low_stock_items': low_stock_items,
                    'recent_orders': recent_orders,
                    'popular_items': popular_items
                }
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Dashboard computation error: {str(e)}'}), 500
    finally:
        conn.close()

@reports_bp.route('/sales-summary', methods=['GET'])
@reports_bp.route('/sales', methods=['GET'])
@staff_required
def sales_summary():
    """
    Date-based sales summary with daily trends, category revenue, and payment method breakdowns.
    """
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date, date_err = validate_date_range(start_str, end_str)
    if date_err:
        return jsonify({'success': False, 'message': date_err}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            date_sql = ""
            date_params = []
            if start_date and end_date:
                date_sql = " AND DATE(o.created_at) BETWEEN %s AND %s"
                date_params.extend([start_date, end_date])
            elif start_date:
                date_sql = " AND DATE(o.created_at) >= %s"
                date_params.append(start_date)
            elif end_date:
                date_sql = " AND DATE(o.created_at) <= %s"
                date_params.append(end_date)
            else:
                date_sql = " AND o.created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"

            # Daily sales trends
            cur.execute(f"""
                SELECT DATE(o.created_at) as sale_date,
                       COUNT(o.order_id) as order_count,
                       COALESCE(SUM(o.total_amount), 0) as daily_total,
                       COALESCE(SUM(CASE WHEN p.status = 'Completed' THEN o.total_amount ELSE 0 END), 0) as settled_total
                FROM orders o
                LEFT JOIN payments p ON o.order_id = p.order_id
                WHERE o.status != 'Cancelled' {date_sql}
                GROUP BY DATE(o.created_at)
                ORDER BY sale_date ASC;
            """, date_params)
            trends = cur.fetchall()
            for tr in trends:
                tr['daily_total'] = float(tr['daily_total'])
                tr['settled_total'] = float(tr['settled_total'])
                tr['sale_date'] = str(tr['sale_date'])

            # Category revenue breakdown
            cur.execute(f"""
                SELECT c.category_name,
                       COALESCE(SUM(od.subtotal), 0) as revenue,
                       COALESCE(SUM(od.quantity), 0) as items_sold
                FROM categories c
                LEFT JOIN menu m ON c.category_id = m.category_id
                LEFT JOIN order_details od ON m.menu_id = od.menu_id
                LEFT JOIN orders o ON od.order_id = o.order_id AND o.status != 'Cancelled' {date_sql}
                GROUP BY c.category_id, c.category_name
                ORDER BY revenue DESC;
            """, date_params)
            cat_breakdown = cur.fetchall()
            for c in cat_breakdown:
                c['revenue'] = float(c['revenue'])
                c['items_sold'] = int(c['items_sold'])

            # Payment method breakdown
            cur.execute("""
                SELECT method, status, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                FROM payments
                GROUP BY method, status;
            """)
            payments_breakdown = cur.fetchall()
            for p in payments_breakdown:
                p['total'] = float(p['total'])

            return jsonify({
                'success': True,
                'data': {
                    'daily_trends': trends,
                    'category_breakdown': cat_breakdown,
                    'payment_breakdown': payments_breakdown
                }
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Sales summary error: {str(e)}'}), 500
    finally:
        conn.close()
