#!/usr/bin/env python3
"""
Cleanup script to delete all inspections, action plans, and jobs from the database.
Use with caution - this will delete ALL data!
"""
import sys
from src.app import app
from src.database import get_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem, Job

def cleanup_all_data():
    """Delete all inspections, action plans, items, and jobs."""
    with app.app_context():
        db = next(get_db())

        try:
            # Count before deletion
            inspection_count = db.query(Inspection).count()
            action_plan_count = db.query(ActionPlan).count()
            item_count = db.query(ActionPlanItem).count()
            job_count = db.query(Job).count()

            print(f"\n📊 Current Data:")
            print(f"  - Inspections: {inspection_count}")
            print(f"  - Action Plans: {action_plan_count}")
            print(f"  - Action Plan Items: {item_count}")
            print(f"  - Jobs: {job_count}")

            if inspection_count == 0 and job_count == 0:
                print("\n✅ Database is already clean!")
                return

            # Confirm deletion
            print(f"\n⚠️  WARNING: This will DELETE ALL data!")
            response = input("Type 'DELETE' to confirm: ")

            if response != 'DELETE':
                print("❌ Cancelled.")
                return

            print("\n🗑️  Deleting data...")

            # Delete in correct order (foreign key constraints)
            # 1. Action Plan Items (references action_plans)
            deleted_items = db.query(ActionPlanItem).delete()
            print(f"  ✅ Deleted {deleted_items} action plan items")

            # 2. Action Plans (references inspections)
            deleted_plans = db.query(ActionPlan).delete()
            print(f"  ✅ Deleted {deleted_plans} action plans")

            # 3. Inspections
            deleted_inspections = db.query(Inspection).delete()
            print(f"  ✅ Deleted {deleted_inspections} inspections")

            # 4. Jobs
            deleted_jobs = db.query(Job).delete()
            print(f"  ✅ Deleted {deleted_jobs} jobs")

            # Commit changes
            db.commit()

            print("\n✅ All data successfully deleted!")
            print("\nℹ️  Note: Companies, establishments, and users were preserved.")

        except Exception as e:
            print(f"\n❌ Error during cleanup: {e}")
            db.rollback()
            raise
        finally:
            db.close()

if __name__ == '__main__':
    cleanup_all_data()
