
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import create_app
from src.database import db
from sqlalchemy import text

app = create_app()

def create_app_config_table():
    with app.app_context():
        # Check if table exists
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='app_config';"))
            if result.fetchone():
                print("Table 'app_config' already exists.")
                return

        # Create table
        print("Creating table 'app_config'...")
        with db.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE app_config (
                    key VARCHAR PRIMARY KEY,
                    value VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
        print("Table 'app_config' created successfully.")

if __name__ == "__main__":
    create_app_config_table()
