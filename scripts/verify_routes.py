
import sys
import os
from flask import Flask, url_for

# Add src to path
sys.path.append(os.getcwd())

def verify_routes():
    print("🔍 Verificando integridade das rotas...")
    try:
        from src.app import create_app
        app = create_app()
    except Exception as e:
        print(f"❌ Falha crítica ao inicializar app para teste: {e}")
        return False

    with app.test_request_context():
        # List of critical expected endpoints to verify existence
        critical_endpoints = [
            'manager.dashboard_manager',
            'admin.index',
            'auth.login',
            'root' 
        ]
        
        missing = []
        for endpoint in critical_endpoints:
            try:
                # Try to build URL (will fail if endpoint doesn't exist)
                url = url_for(endpoint)
                print(f"✅ Rota OK: {endpoint} -> {url}")
            except Exception as e:
                print(f"❌ Rota QUEBRADA: {endpoint} - {e}")
                missing.append(endpoint)
                
        if missing:
            print("🚨 ERRO: Rotas críticas não encontradas ou inválidas!")
            return False
            
    print("✨ Todas as rotas verificado com sucesso.")
    return True

if __name__ == "__main__":
    if not verify_routes():
        sys.exit(1)
