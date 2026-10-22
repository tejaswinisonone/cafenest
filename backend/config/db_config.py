import os
import pymysql
from pymysql.cursors import DictCursor

DB_HOST = os.getenv('MYSQL_HOST', 'localhost')
DB_USER = os.getenv('MYSQL_USER', 'root')
DB_PASS = os.getenv('MYSQL_PASSWORD', 'Teju_sonone2007')
DB_NAME = os.getenv('MYSQL_DB', 'cafenest_db')
DB_PORT = int(os.getenv('MYSQL_PORT', 3306))

def get_db_connection():
    """Returns a MySQL connection with autocommit disabled for explicit transaction control."""
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=False
    )
    return connection
