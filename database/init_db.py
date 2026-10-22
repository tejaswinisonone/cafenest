import os
import pymysql

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Teju_sonone2007'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'charset': 'utf8mb4'
}

def execute_sql_file(cursor, file_path):
    print(f"Reading {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Split statements by semicolon, ignoring statements inside strings/blocks if any
    # Clean and split
    statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
    for stmt in statements:
        if stmt:
            cursor.execute(stmt)

def init_database():
    print("Connecting to MySQL...")
    conn = pymysql.connect(**DB_CONFIG)
    conn.autocommit(True)
    cursor = conn.cursor()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_file = os.path.join(base_dir, 'schema.sql')
    seed_file = os.path.join(base_dir, 'seed.sql')

    print("Applying schema.sql...")
    execute_sql_file(cursor, schema_file)
    print("Schema applied successfully!")

    print("Applying seed.sql...")
    execute_sql_file(cursor, seed_file)
    print("Seed data loaded successfully!")

    # Verify tables
    cursor.execute("USE `cafenest_db`;")
    cursor.execute("SHOW TABLES;")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"\nCreated {len(tables)} tables in cafenest_db:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM `{t}`;")
        count = cursor.fetchone()[0]
        print(f"  - {t}: {count} rows")

    cursor.close()
    conn.close()
    print("\nDatabase initialization complete!")

if __name__ == '__main__':
    init_database()
