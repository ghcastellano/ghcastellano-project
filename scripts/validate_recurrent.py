#!/usr/bin/env python3
import os
import re
import sys

# Cores para output
RED = '\033[91m'
GREEN = '\033[92m'
RESET = '\033[0m'

def check_file_content(path, pattern, error_msg, should_exist=True):
    if not os.path.exists(path):
        print(f"{RED}[FAIL] Arquivo não encontrado: {path}{RESET}")
        return False
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    match = re.search(pattern, content)
    if should_exist and not match:
        print(f"{RED}[FAIL] {error_msg} em {path}{RESET}")
        return False
    elif not should_exist and match:
        print(f"{RED}[FAIL] {error_msg} em {path}{RESET}")
        return False
        
    print(f"{GREEN}[PASS] {path} verificado.{RESET}")
    return True

def main():
    print("🔍 Iniciando Validação de Problemas Recorrentes...\n")
    all_passed = True
    
    # 1. Validação Zero Cost (Deploy Script)
    print("--- 1. Zero Cost Architecture ---")
    # Deve conter limpeza mantendo apenas 2 versoes (tail -n +3)
    if not check_file_content(
        '.github/workflows/deploy.yml', 
        r'tail -n \+3', 
        "Script de deploy deve manter APENAS 2 versões (tail -n +3)"):
        all_passed = False

    # 2. Validação Secrets
    print("\n--- 2. Segurança ---")
    # Pattern simples para detectar chaves hardcoded (exemplo basico)
    # Evitar detectar o proprio script
    suspicious = r'(sk-[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z-_]{35})'
    # Procura em .py e .html
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith(('.py', '.html')):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    if re.search(suspicious, f.read()):
                         print(f"{RED}[FAIL] Possível chave secreta encontrada em {path}{RESET}")
                         all_passed = False

    # 3. Validação Flask Imports
    print("\n--- 3. Estabilidade Código ---")
    # Verificar se get_flashed_messages está importado se for usado
    # (Simplificação: apenas checa app.py por enquanto)
    # check_file_content('src/app.py', r'get_flashed_messages', "get_flashed_messages deve ser importado/usado")

    # 4. Validação AJAX (Exploratória)
    print("\n--- 4. UX/AJAX ---")
    # Verificar se templates de dashboard tem o script genérico ou handlers
    if not check_file_content(
        'src/templates/admin_dashboard.html', 
        r'GENERIC AJAX FORM HANDLER', 
        "Dashboard Admin deve ter Handler AJAX Genérico"):
        all_passed = False
        
    if not check_file_content(
        'src/templates/dashboard_manager_v2.html', 
        r'GENERIC AJAX FORM HANDLER', 
        "Dashboard Manager V2 deve ter Handler AJAX Genérico"):
        all_passed = False

    print("\n------------------------------------------------")
    if all_passed:
        print(f"{GREEN}✅ TUDO OK! O projeto segue as regras de ouro.{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}❌ FALHA NA VALIDAÇÃO! Corrija os itens acima.{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
