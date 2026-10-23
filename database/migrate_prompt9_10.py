"""
CaféNest — Migration for Prompt 9 & 10
Safely adds:
1. `cafe_name` to `cafe_tables` if missing.
2. `created_at` to `cafe_tables` if missing.
3. Party size column to orders if desired or party size validation support.
"""

from backend.config.db_config import get_db_connection

def run_migration():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check columns in cafe_tables
            cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cafe_tables';")
            table_cols = [r['COLUMN_NAME'] for r in cur.fetchall()]

            if 'cafe_name' not in table_cols:
                print("Adding 'cafe_name' to cafe_tables...")
                cur.execute("ALTER TABLE cafe_tables ADD COLUMN cafe_name VARCHAR(100) NOT NULL DEFAULT 'CaféNest Artisan Roastery';")
            else:
                print("'cafe_name' already exists in cafe_tables.")

            if 'created_at' not in table_cols:
                print("Adding 'created_at' to cafe_tables...")
                cur.execute("ALTER TABLE cafe_tables ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;")
            else:
                print("'created_at' already exists in cafe_tables.")

            # Check if party_size column exists in orders
            cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders';")
            order_cols = [r['COLUMN_NAME'] for r in cur.fetchall()]
            if 'party_size' not in order_cols:
                print("Adding 'party_size' to orders...")
                cur.execute("ALTER TABLE orders ADD COLUMN party_size INT DEFAULT 1;")
            else:
                print("'party_size' already exists in orders.")

            conn.commit()
            print("Migration for Prompt 9 & 10 completed successfully!")
    except Exception as e:
        conn.rollback()
        print("Migration failed:", e)
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()
