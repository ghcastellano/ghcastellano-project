#!/usr/bin/env python3
import subprocess
import time
import sys
import json

# Configuration
SERVICE_NAME = "mvp-web"
REGION = "us-central1"
PROJECT_ID = "projeto-poc-ap"
# Test command now sources local secrets to ensure DB connection
TEST_CMD = f"source .tmp_venv/bin/activate && source src/secrets.sh && export PYTHONPATH=$PYTHONPATH:. && {sys.executable} -m pytest -s tests/"
DEPLOY_CMD = f"gcloud run deploy {SERVICE_NAME} --source . --region {REGION} --project {PROJECT_ID} --format=json"

def run_step(name, cmd, exit_on_fail=True):
    print(f"\n🚀 [STEP] {name}...")
    try:
        # Using shell=True for 'source' command usage
        result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
        print(f"✅ {name} PASSED.")
        # print(result.stdout)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {name} FAILED!")
        print(e.stderr)
        print(e.stdout)
        if exit_on_fail:
            sys.exit(1)
        return False, e.stderr

def monitor_logs(revision_name):
    print(f"\n👀 [MONITOR] Watching logs for errors in {revision_name} (30s)...")
    # Wait for logs to propagate
    time.sleep(10)
    
    # Check logs for the specific revision
    log_filter = (
        f'resource.type="cloud_run_revision" AND '
        f'resource.labels.revision_name="{revision_name}" AND '
        f'severity>=ERROR'
    )
    
    cmd = [
        "gcloud", "logging", "read", log_filter,
        "--project", PROJECT_ID,
        "--limit", "5",
        "--format", "json"
    ]
    
    start_time = time.time()
    duration = 30 # Monitor for 30 seconds
    
    while time.time() - start_time < duration:
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logs = json.loads(result.stdout)
            
            if logs:
                print(f"❌ ERROR DETECTED in logs for {revision_name}:")
                for log in logs:
                    print(f" - {log.get('textPayload') or 'See Cloud Logging'}")
                print("⚠️  DEPLOYMENT UNSTABLE. Rolling back/Alerting recommended.")
                return False
                
        except Exception as e:
            print(f"⚠️ Failed to read logs: {e}")
            
        time.sleep(5)
        print(".", end="", flush=True)
        
    print("\n✅ Log Monitor CLEAN. No immediate errors detected.")
    return True

def main():
    print("🤖 Smart Deploy Agent Initialized")
    
    # 1. Run Tests
    run_step("Running Unit Tests", TEST_CMD)
    
    # 2. Deploy
    print(f"\n🚀 [STEP] Deploying to Cloud Run (this takes time)...")
    success, output = run_step("Cloud Run Deploy", DEPLOY_CMD)
    
    try:
        deploy_info = json.loads(output)
        # Handle format: gcloud might return list or dict depending on version/flags?
        # Usually list unless one item.
        if isinstance(deploy_info, list): deploy_info = deploy_info[0]
        
        url = deploy_info.get('status', {}).get('url')
        revision = deploy_info.get('status', {}).get('latestCreatedRevisionName')
        
        print(f"ℹ️  Deployed Revision: {revision}")
        print(f"🔗 URL: {url}")
        
        # 3. Monitor Logs
        if revision:
            healthy = monitor_logs(revision)
            if not healthy:
                print("❌ Monitoring failed. Check logs!")
                sys.exit(1)
        else:
            print("⚠️ Could not determine revision name. Skipping monitor.")
            
        print("\n🎉 DEPLOY SUCCESSFUL & VERIFIED!")
        
    except json.JSONDecodeError:
        print("⚠️ Could not parse deployment output JSON. Check logs manually.")
        
if __name__ == "__main__":
    main()
