
import sys
import psycopg2
from urllib.parse import urlparse

import os

# Use environment variable for security
DB_URL = os.getenv("DATABASE_URL")

def test_conn():
    print(f"🔌 Testing Connection to: {DB_URL.split('@')[1]}")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        print("✅ Connection SUCCESS! The password is CORRECT.")
        conn.close()
    except Exception as e:
        print(f"❌ Connection FAILED: {e}")
        
if __name__ == "__main__":
    test_conn()
