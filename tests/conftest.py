
import pytest
import os
from src.app import app
from src.database import init_db, db_session

@pytest.fixture
def client():
    # Configure app for testing
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for easier API testing
    
    # Use an in-memory SQLite DB for speed and isolation, OR mock the real DB
    # For this MVP context, we might rely on the real DB connection IF we are careful,
    # OR better: Mock the session.
    # Let's try to trust the env vars for now but be cautious.
    
    with app.test_client() as client:
        with app.app_context():
            # Create tables if not exist (optional, danger if prod DB!)
            # init_db() 
            yield client
            
@pytest.fixture
def session():
    # Return database session
    return db_session
