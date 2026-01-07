
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

print("⏳ [RUNNER] Importing src.app...")
from src.app import app
print("✅ [RUNNER] Import complete.")

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8080))
        print(f"🚀 [RUNNER] STARTING APP ON PORT {port}...")
        app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False) # Disable reloader to avoid child process confusion
    except Exception as e:
        print(f"❌ [RUNNER] ERROR: {e}")
