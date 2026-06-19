"""
Run this script to create tables only (no CREATE DATABASE).
Use with PlanetScale or any managed MySQL where you don't have permission to create databases.

Usage (after setting env vars or copying .env):
    python init_tables.py

It reads DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT from environment.
"""
import os
import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'inventory_system'),
    'port': int(os.environ.get('DB_PORT', 3306))
}

TABLES = {}
TABLES['users'] = (
    "CREATE TABLE IF NOT EXISTS users ("
    "  id INT AUTO_INCREMENT PRIMARY KEY,"
    "  username VARCHAR(255) UNIQUE NOT NULL,"
    "  password_hash VARCHAR(255) NOT NULL,"
    "  full_name VARCHAR(255) NOT NULL,"
    "  role VARCHAR(50) NOT NULL DEFAULT 'admin',"
    "  profile_pic VARCHAR(255),"
    "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ") ENGINE=InnoDB"
)

# Note: We intentionally omit foreign key constraints on some serverless providers
# because they may not support them. If your provider supports foreign keys, add
# them later via ALTER TABLE.

TABLES['inventory'] = (
    "CREATE TABLE IF NOT EXISTS inventory ("
    "  id INT AUTO_INCREMENT PRIMARY KEY,"
    "  description VARCHAR(500) NOT NULL,"
    "  model VARCHAR(255),"
    "  specs TEXT,"
    "  date_acquired DATE,"
    "  amount DECIMAL(10, 2),"
    "  rv_number VARCHAR(255) UNIQUE NOT NULL,"
    "  po_number VARCHAR(255),"
    "  acquired_by VARCHAR(255),"
    "  location_installed VARCHAR(500),"
    "  remarks TEXT,"
    "  date_entry DATETIME DEFAULT CURRENT_TIMESTAMP,"
    "  entry_by VARCHAR(255),"
    "  user_id INT,"
    "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    ") ENGINE=InnoDB"
)


def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("Connected to database", DB_CONFIG['database'])

        for name, ddl in TABLES.items():
            print(f"Creating table {name}...")
            cursor.execute(ddl)

        conn.commit()
        cursor.close()
        conn.close()
        print("Tables created successfully")
    except Error as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
