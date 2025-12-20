
import sys
import os
import io
import contextlib
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.getcwd())

# MOCK Binary Dependencies (WeasyPrint) to allow local sanity check
sys.modules['weasyprint'] = MagicMock()
sys.modules['weasyprint.text.fonts'] = MagicMock() # Ensure submodules work


def sanity_check():
    print("🏥 Executing Zero Defect Sanity Check...")
    
    # 1. Check Imports
    try:
        from src.app import app
        print("✅ App Import: OK")
    except Exception as e:
        print(f"❌ App Import FAILED: {e}")
        return False

    # 2. Check Critical Routes
    with app.test_request_context():
        # List of critical expected endpoints to verify existence
        critical_endpoints = [
            'manager.dashboard_manager',
            'admin.index',
            'auth.login',
            'root',
            'admin.update_manager'
        ]
        
        missing = []
        for endpoint in critical_endpoints:
            try:
                from flask import url_for
                # Try to build URL with dummy params where needed
                if endpoint == 'admin.update_manager':
                    url = url_for(endpoint, user_id='00000000-0000-0000-0000-000000000000')
                else:
                    url = url_for(endpoint)
                print(f"  - Route {endpoint}: OK ({url})")
            except Exception as e:
                print(f"❌ Route {endpoint} MISSING or ERROR: {e}")
                missing.append(endpoint)
                
        if missing:
            return False

    # 3. Check HTML Syntax (Basic)
    # Check if dashboard_manager.html has unclosed aside (regex or simple check)
    # We can read the file directly
    try:
        with open('src/templates/dashboard_manager.html', 'r') as f:
            content = f.read()
            if '<aside' in content and '</aside>' not in content:
                print("❌ HTML Check: dashboard_manager.html has UNCLOSED <aside> tag!")
                return False
            print("✅ HTML Check: OK")
    except Exception as e:
        print(f"⚠️ Could not check HTML: {e}")

    print("✅ All Systems Go.")
    return True

if __name__ == "__main__":
    if not sanity_check():
        sys.exit(1)
