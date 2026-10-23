import os
import sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.config.db_config import get_db_connection

def migrate():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check existing columns in orders table
            cur.execute("DESCRIBE orders;")
            columns = [row['Field'] for row in cur.fetchall()]
            
            if 'customer_name' not in columns:
                cur.execute("ALTER TABLE orders ADD COLUMN customer_name VARCHAR(100) DEFAULT NULL AFTER customer_id;")
                print("Added customer_name column.")
                
            if 'customer_phone' not in columns:
                cur.execute("ALTER TABLE orders ADD COLUMN customer_phone VARCHAR(20) DEFAULT NULL AFTER customer_name;")
                print("Added customer_phone column.")

            if 'customer_email' not in columns:
                cur.execute("ALTER TABLE orders ADD COLUMN customer_email VARCHAR(150) DEFAULT NULL AFTER customer_phone;")
                print("Added customer_email column.")

            if 'idempotency_key' not in columns:
                cur.execute("ALTER TABLE orders ADD COLUMN idempotency_key VARCHAR(100) DEFAULT NULL UNIQUE AFTER special_instructions;")
                print("Added idempotency_key column with UNIQUE constraint.")

            conn.commit()
            print("Migration complete. Updated columns in orders table:")
            cur.execute("DESCRIBE orders;")
            for col in cur.fetchall():
                print(f"  - {col['Field']}: {col['Type']} (Null: {col['Null']})")
    except Exception as e:
        conn.rollback()
        print("Migration error:", e)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
