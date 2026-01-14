import subprocess
import time
import requests
import sys
import os

def run_smoke_test():
    print("🔥 Iniciando Smoke Test (Local Server)...")
    
    # 1. Start the app in background
    # Ensure PYTHONPATH is set
    env = os.environ.copy()
    env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + os.getcwd()
    
    print("⏳ Iniciando servidor Flask...")
    process = subprocess.Popen(
        ["python3", "src/app.py"], 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid # Allow killing the whole group
    )
    
    # 2. Wait for startup
    time.sleep(10)
    
    base_url = "http://127.0.0.1:8080"
    endpoints_to_check = [
        ("/", 200),
        ("/auth/login", 200),
        # /dashboard/manager might redirect to login if not auth, which is a success (302) or 200 if unprotected
        # We expect at least a valid HTTP response, not 500
        ("/dashboard/manager", [200, 302, 401]) 
    ]
    
    success = True
    
    try:
        # Check if process is still alive
        if process.poll() is not None:
             print("❌ Servidor caiu imediatamente. Verifique os logs.")
             stderr = process.stderr.read().decode()
             print(stderr)
             return False

        for endpoint, expected in endpoints_to_check:
            url = f"{base_url}{endpoint}"
            try:
                resp = requests.get(url, timeout=5)
                status = resp.status_code
                
                valid = False
                if isinstance(expected, list):
                    valid = status in expected
                else:
                    valid = status == expected
                
                if valid:
                    print(f"✅ {endpoint} retornou code {status}")
                else:
                    print(f"❌ {endpoint} falhou! Esperado {expected}, recebeu {status}")
                    success = False
            
            except requests.exceptions.ConnectionError:
                print(f"❌ Falha de conexão ao tentar acessar {url}. Servidor está rodando?")
                success = False
                break
                
    finally:
        print("🛑 Parando servidor de teste...")
        os.killpg(os.getpgid(process.pid), 15)  # Kill process group
    
    return success

if __name__ == "__main__":
    if run_smoke_test():
        print("\n🚀 Smoke Test passou! Telas principais carregando.")
        sys.exit(0)
    else:
        print("\n❌ Smoke Test falhou.")
        sys.exit(1)
