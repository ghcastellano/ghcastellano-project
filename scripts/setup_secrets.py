
import os
import shutil

def setup_secrets():
    print("🔐 Verificando configuração de segredos locais (Zero Cost Dev)...")
    
    # 1. Verifica se .env existe
    if not os.path.exists('.env'):
        print("⚠️  Arquivo '.env' não encontrado.")
        if os.path.exists('.env.example'):
            print("📄 Criando '.env' a partir de '.env.example'...")
            shutil.copy('.env.example', '.env')
            print("✅ Arquivo criado.")
            print("\n🚨 AÇÃO NECESSÁRIA: Abra o arquivo '.env' e preencha as chaves reais.")
            print("   (Peça as chaves para o administrador do projeto ou use o 1Password)")
        else:
            print("❌ Erro: '.env.example' também não encontrado. Verifique o repositório.")
    else:
        print("✅ Arquivo '.env' já existe.")

    # 2. Verifica credenciais do Google User (Zero Cost OAuth)
    if not os.path.exists('user_credentials.json'):
        print("\n⚠️  'user_credentials.json' (Token de Usuário) não encontrado.")
        print("   Este projeto usa seu próprio usuário Google para economizar quota.")
        print("   Execute: python scripts/generate_token.py")
    else:
        print("✅ 'user_credentials.json' encontrado.")
        
    print("\n---------------------------------------------------------")
    print("💡 DICA: Em Produção (Cloud Run), usamos GitHub Secrets.")
    print("   Locamente, usamos apenas este .env (gitignored).")
    print("---------------------------------------------------------")

if __name__ == "__main__":
    setup_secrets()
