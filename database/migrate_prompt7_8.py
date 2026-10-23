"""
CaféNest — Migration for Prompt 7 & 8
Safely adds:
1. `cafe_name` and `discount_amount` columns to `orders` table if missing.
2. `item_name` column to `order_details` table if missing.
3. Backfills `item_name` in `order_details` from `menu` table.
4. Creates `order_status_history` table for auditing order state transitions.
"""

from backend.config.db_config import get_db_connection

def run_migration():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Check and add columns to orders table
            cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders';")
            orders_cols = [r['COLUMN_NAME'] for r in cur.fetchall()]

            if 'cafe_name' not in orders_cols:
                print("Adding 'cafe_name' to orders...")
                cur.execute("ALTER TABLE orders ADD COLUMN cafe_name VARCHAR(100) NOT NULL DEFAULT 'CaféNest Artisan Roastery';")
            else:
                print("'cafe_name' already exists in orders.")

            if 'discount_amount' not in orders_cols:
                print("Adding 'discount_amount' to orders...")
                cur.execute("ALTER TABLE orders ADD COLUMN discount_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00;")
            else:
                print("'discount_amount' already exists in orders.")

            # 2. Check and add item_name to order_details table
            cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'order_details';")
            details_cols = [r['COLUMN_NAME'] for r in cur.fetchall()]

            if 'item_name' not in details_cols:
                print("Adding 'item_name' to order_details...")
                cur.execute("ALTER TABLE order_details ADD COLUMN item_name VARCHAR(150) DEFAULT NULL;")
            else:
                print("'item_name' already exists in order_details.")

            # Backfill item_name for any existing rows where item_name is NULL
            cur.execute("""
                UPDATE order_details od
                JOIN menu m ON od.menu_id = m.menu_id
                SET od.item_name = m.name
                WHERE od.item_name IS NULL OR od.item_name = '';
            """)
            print("Backfilled item_name in order_details.")

            # 3. Create order_status_history table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS `order_status_history` (
                    `history_id` INT AUTO_INCREMENT PRIMARY KEY,
                    `order_id` INT NOT NULL,
                    `previous_status` VARCHAR(50) DEFAULT NULL,
                    `new_status` VARCHAR(50) NOT NULL,
                    `changed_by_staff_id` INT DEFAULT NULL,
                    `notes` VARCHAR(255) DEFAULT NULL,
                    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT `fk_osh_order` FOREIGN KEY (`order_id`) 
                        REFERENCES `orders` (`order_id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_osh_staff` FOREIGN KEY (`changed_by_staff_id`) 
                        REFERENCES `staff` (`staff_id`) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            print("Table 'order_status_history' verified/created.")

            conn.commit()
            print("Migration completed successfully!")
    except Exception as e:
        conn.rollback()
        print("Migration failed:", e)
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()
