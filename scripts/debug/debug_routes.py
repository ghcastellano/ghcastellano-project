
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from flask import Flask

try:
    from src.app import app
    print("✅ App imported successfully")
except Exception as e:
    print(f"❌ Failed to import app: {e}")
    sys.exit(1)

print("\n--- Registered Blueprints ---")
print(app.blueprints.keys())

print("\n--- URL Map ---")
found_admin = False
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule}")
    if rule.endpoint == 'admin.index':
        found_admin = True

if found_admin:
    print("\n✅ 'admin.index' found in URL map.")
else:
    print("\n❌ 'admin.index' NOT found in URL map.")
