#!/usr/bin/env python3
import os
import sys
import re
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("verify_deploy")

def check_secrets():
    """Scans for potential hardcoded secrets in the src directory."""
    logger.info("🔍 Checking for hardcoded secrets...")
    patterns = {
        'OpenAI Key': r'sk-[a-zA-Z0-9]{32,}',
        'GCP Key': r'AIza[0-9A-Za-z-_]{35}',
        'Generic Secret': r'(?i)(password|secret|key|token)\s*[:=]\s*["\'][a-zA-Z0-9]{15,}["\']'
    }
    
    src_dir = Path("src")
    scripts_dir = Path("scripts")
    found_issues = 0
    
    for directory in [src_dir, scripts_dir]:
        if not directory.exists(): continue
        for path in directory.rglob("*.py"):
            if path.name == "verify_deploy.py": continue
            content = path.read_text()
            for name, pattern in patterns.items():
                if re.search(pattern, content):
                    # Filter out known safe defaults if any
                    if 'dev_secret_key' in content: continue
                    logger.warning(f"❌ Potential {name} found in {path}")
                    found_issues += 1
    
    return found_issues == 0

def check_env_vars():
    """Checks if required environment variables are at least defined in the runtime context."""
    logger.info("🔍 Checking environment variables...")
    required = [
        "DATABASE_URL",
        "OPENAI_API_KEY",
        "GCP_PROJECT_ID",
        "FOLDER_ID_01_ENTRADA_RELATORIOS"
    ]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.warning(f"⚠️ Missing required env vars in current shell: {', '.join(missing)}")
        # We don't exit 1 here yet because they might be in Secret Manager
        return False
    return True

def check_syntax():
    """Runs a quick syntax check on all python files."""
    logger.info("🔍 Checking Python syntax...")
    import compileall
    success = compileall.compile_dir("src", quiet=1)
    if not success:
        logger.error("❌ Syntax errors found in src directory!")
        return False
    return True

def main():
    logger.info("🚀 Starting Pre-deployment Verification")
    
    syntax_ok = check_syntax()
    secrets_ok = check_secrets()
    env_ok = check_env_vars()
    
    if not syntax_ok:
        logger.error("🚫 Deployment aborted: Syntax errors.")
        sys.exit(1)
        
    if not secrets_ok:
        logger.error("🚫 Deployment aborted: Potential secrets found in code.")
        sys.exit(1)
        
    if not env_ok:
        logger.warning("📝 Note: Some env vars are missing from the local environment. Ensure they are configured in Cloud Run/Secret Manager.")

    logger.info("✨ Pre-deployment verification PASSED.")

if __name__ == "__main__":
    main()
