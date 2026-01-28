import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.models_db import ActionPlanItem
from sqlalchemy import text

def fix_null_scores():
    print("Connecting to DB...")
    session = database.db_session()
    try:
        # Check count of nulls
        count = session.query(ActionPlanItem).filter(ActionPlanItem.original_score == None).count()
        print(f"Found {count} items with null original_score.")
        
        if count > 0:
            print("Updating nulls to 0.0...")
            # Use bulk update for efficiency
            session.query(ActionPlanItem).filter(ActionPlanItem.original_score == None).update({ActionPlanItem.original_score: 0.0}, synchronize_session=False)
            session.commit()
            print("Update complete.")
        else:
            print("No items to update.")
            
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    fix_null_scores()
