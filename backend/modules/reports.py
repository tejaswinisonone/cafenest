from flask import Blueprint, request, jsonify
from backend.config.db_config import get_db_connection
from backend.middleware.auth_middleware import staff_required

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/dashboard', methods=['GET'])
@staff_required
def dashboard_metrics():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Total sales today & orders count today
            cur.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as today_sales,
                       COUNT(order_id) as today_orders
                FROM orders
                WHERE DATE(created_at) = CURDATE() AND status != 'Cancelled';
            """)
            today_data = cur.fetchone()

            # All-time sales
            cur.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as all_time_sales,
                       COUNT(order_id) as all_time_orders
                FROM orders
                WHERE status != 'Cancelled';
            """)
            all_time_data = cur.fetchone()

            # 2. Active orders count (Pending, Confirmed, Preparing, Ready)
            cur.execute("""
                SELECT COUNT(*) as active_count
                FROM orders
                WHERE status IN ('Pending', 'Confirmed', 'Preparing', 'Ready');
            """)
            active_res = cur.fetchone()

            # 3. Tables summary
            cur.execute("""
                SELECT COUNT(*) as total_tables,
                       SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied_tables,
                       SUM(CASE WHEN status = 'Reserved' THEN 1 ELSE 0 END) as reserved_tables,
                       SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available_tables
                FROM cafe_tables;
            """)
            tables_data = cur.fetchone()

            # 4. Low stock count
            cur.execute("""
                SELECT COUNT(*) as low_stock_count
                FROM inventory
                WHERE quantity <= reorder_level;
            """)
            low_stock_data = cur.fetchone()

            # 5. Recent orders (last 8)
            cur.execute("""
                SELECT o.order_id, o.order_reference, o.order_type, o.status,
                       o.total_amount, o.created_at,
                       t.table_number,
                       c.name as customer_name,
                       p.method as payment_method
                FROM orders o
                LEFT JOIN cafe_tables t ON o.table_id = t.table_id
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                LEFT JOIN payments p ON o.order_id = p.order_id
                ORDER BY o.created_at DESC LIMIT 8;
            """)
            recent_orders = cur.fetchall()
            for r in recent_orders:
                r['total_amount'] = float(r['total_amount'])
                r['created_at'] = r['created_at'].strftime('%H:%M:%S') if r['created_at'] else ''

            # 6. Top popular menu items
            cur.execute("""
                SELECT m.menu_id, m.name, c.category_name, m.price,
                       COALESCE(SUM(od.quantity), 0) as total_sold,
                       COALESCE(SUM(od.subtotal), 0) as total_revenue
                FROM menu m
                JOIN categories c ON m.category_id = c.category_id
                LEFT JOIN order_details od ON m.menu_id = od.menu_id
                GROUP BY m.menu_id
                ORDER BY total_sold DESC, total_revenue DESC LIMIT 5;
            """)
            popular_items = cur.fetchall()
            for p in popular_items:
                p['price'] = float(p['price'])
                p['total_sold'] = int(p['total_sold'])
                p['total_revenue'] = float(p['total_revenue'])

            return jsonify({
                'success': True,
                'data': {
                    'today_sales': float(today_data['today_sales']),
                    'today_orders': int(today_data['today_orders']),
                    'all_time_sales': float(all_time_data['all_time_sales']),
                    'all_time_orders': int(all_time_data['all_time_orders']),
                    'active_orders': int(active_res['active_count']),
                    'tables': {
                        'total': int(tables_data['total_tables']),
                        'occupied': int(tables_data['occupied_tables'] or 0),
                        'reserved': int(tables_data['reserved_tables'] or 0),
                        'available': int(tables_data['available_tables'] or 0)
                    },
                    'low_stock_count': int(low_stock_data['low_stock_count']),
                    'recent_orders': recent_orders,
                    'popular_items': popular_items
                }
            })
    finally:
        conn.close()

@reports_bp.route('/sales', methods=['GET'])
@staff_required
def sales_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Sales by Category
            cur.execute("""
                SELECT c.category_name, 
                       COALESCE(SUM(od.subtotal), 0) as revenue,
                       COALESCE(SUM(od.quantity), 0) as items_sold
                FROM categories c
                LEFT JOIN menu m ON c.category_id = m.category_id
                LEFT JOIN order_details od ON m.menu_id = od.menu_id
                LEFT JOIN orders o ON od.order_id = o.order_id AND o.status != 'Cancelled'
                GROUP BY c.category_id
                ORDER BY revenue DESC;
            """)
            cat_data = cur.fetchall()
            for c in cat_data:
                c['revenue'] = float(c['revenue'])
                c['items_sold'] = int(c['items_sold'])

            # Daily sales for last 7 days
            cur.execute("""
                SELECT DATE(created_at) as order_date,
                       COALESCE(SUM(total_amount), 0) as daily_total,
                       COUNT(order_id) as order_count
                FROM orders
                WHERE status != 'Cancelled' AND created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY order_date ASC;
            """)
            daily_data = cur.fetchall()
            for d in daily_data:
                d['daily_total'] = float(d['daily_total'])
                d['order_date'] = str(d['order_date'])

            # Payment methods breakdown
            cur.execute("""
                SELECT method, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                FROM payments
                WHERE status = 'Completed'
                GROUP BY method;
            """)
            payment_methods = cur.fetchall()
            for p in payment_methods:
                p['total'] = float(p['total'])

            return jsonify({
                'success': True,
                'data': {
                    'category_breakdown': cat_data,
                    'daily_trends': daily_data,
                    'payment_breakdown': payment_methods
                }
            })
    finally:
        conn.close()
