import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from backend.modules.auth import auth_bp
from backend.modules.menu import menu_bp
from backend.modules.orders import orders_bp
from backend.modules.payments import payments_bp
from backend.modules.tables import tables_bp
from backend.modules.inventory import inventory_bp
from backend.modules.staff import staff_bp
from backend.modules.reports import reports_bp

def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'frontend'),
        static_url_path='/frontend'
    )
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cafenest-dbms-secret-key-2026')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    CORS(app, supports_credentials=True)

    # Register API Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(menu_bp, url_prefix='/api/menu')
    app.register_blueprint(orders_bp, url_prefix='/api/orders')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(tables_bp, url_prefix='/api/tables')
    app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
    app.register_blueprint(staff_bp, url_prefix='/api/staff')
    app.register_blueprint(reports_bp, url_prefix='/api/admin')

    # Root route serves index.html
    @app.route('/')
    def index():
        return send_from_directory(BASE_DIR, 'index.html')

    # Frontend pages routes
    @app.route('/<path:path>')
    def serve_static(path):
        # First check root directory (e.g. index.html)
        if os.path.exists(os.path.join(BASE_DIR, path)):
            return send_from_directory(BASE_DIR, path)
        # Check inside frontend/
        if os.path.exists(os.path.join(BASE_DIR, 'frontend', path)):
            return send_from_directory(os.path.join(BASE_DIR, 'frontend'), path)
        return jsonify({'error': 'Page not found'}), 404

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

    return app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app = create_app()
    print(f"=======================================================")
    print(f" CaféNest Backend running on http://127.0.0.1:{port}")
    print(f"=======================================================")
    app.run(host='0.0.0.0', port=port, debug=True)
