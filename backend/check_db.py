import sqlite3
import os

db_path = 'sales.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables in {db_path}: {tables}")
    conn.close()
else:
    print(f"{db_path} does not exist")
