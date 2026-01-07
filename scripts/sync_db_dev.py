
from src.app import app
from src import database
from src.models_db import *
# Import all models to ensure they are registered in metadata
from src.models_db import Inspection, ActionPlan, ActionPlanItem, Job, Establishment, User, Company

with app.app_context():
    try:
        print("Initializing DB...")
        database.init_db() # Explicitly init
        print("Checking tables...")
        # database.db_session.remove() # Clean start
        # Bind engine
        import sqlalchemy
        inspector = sqlalchemy.inspect(database.engine)
        existing = inspector.get_table_names()
        print(f"Existing tables in DEV: {existing}")
        
        print("Creating missing tables...")
        database.Base.metadata.create_all(bind=database.engine)
        print("✅ Tables Created/Verified.")
    except Exception as e:
        print(f"❌ Error: {e}")
