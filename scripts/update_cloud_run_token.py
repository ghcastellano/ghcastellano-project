
import os
import json
import subprocess
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_FILE = "user_credentials.json"
SERVICE_NAME = "mvp-web"
REGION = "us-central1"
PROJECT = "projeto-poc-ap"

def deploy_token():
    if not os.path.exists(TOKEN_FILE):
        print(f"❌ {TOKEN_FILE} not found.")
        return

    print(f"🔑 Reading {TOKEN_FILE}...")
    with open(TOKEN_FILE, 'r') as f:
        # Load and Dump to ensure compact JSON (no newlines)
        token_data = json.load(f)
        token_str = json.dumps(token_data)
    
    print(f"🚀 Updating Cloud Run Service '{SERVICE_NAME}' with User Token...")
    print(f"   (Token Length: {len(token_str)} chars)")

    # Construct command list to avoid shell escaping hell
    cmd = [
        "gcloud", "run", "services", "update", SERVICE_NAME,
        "--project", PROJECT,
        "--region", REGION,
        "--update-env-vars", f"GCP_OAUTH_TOKEN={token_str}"
    ]
    
    try:
        # Use subprocess.run directly
        subprocess.run(cmd, check=True)
        print("\n✅ Sucesso! Cloud Run atualizado com seu Token de Usuário.")
        print("Agora os uploads usarão a SUA cota do Drive (15GB).")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro ao atualizar Cloud Run: {e}")

if __name__ == "__main__":
    deploy_token()
