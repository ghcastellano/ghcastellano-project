import sys
import os

# Mapping of English substrings to Portuguese messages
TRANSLATIONS = {
    "Aumento de limite para 32MB e Zero Idle Traffic": "feat(core): Aumento de limite (32MB) e Tráfego Zero em Ociosidade",
    "remove frontend polling": "fix: remove verificações automáticas (polling) para garantir custo zero",
    "enforce zero cost cleanup": "feat: aplica limpeza de custo zero, melhorias UX e validação",
    "manual drive sync": "feat: sincronização manual do drive e auto-sync no login de admin",
    "restore cron route": "fix: restaura rota cron e melhora detecção de email da service account",
    "ensure auto-patch runs": "fix: garante execução do auto-patch na inicialização (correção crítica)",
    "auto-patch db schema": "fix: auto-patch do esquema do banco e log de email da SA",
    "upload bugs, translate logs": "fix: bugs de upload, tradução de logs, melhorias no painel de admin",
    "Update Secrets Configuration": "chore(deploy): Atualização de Configuração de Segredos",
    "Add robust fallback": "fix: adiciona fallback robusto para SECRET_KEY evitando erro 500",
    "force add missing columns": "fix: força adição de colunas faltantes nas tabelas de empresas/estabelecimentos",
    "remove remaining Supabase": "docs: remove comentários e docstrings restantes sobre Supabase",
    "remove all legacy supabase": "refactor: remove referências legadas e validações do Supabase",
    "sync DATABASE_URL from github": "fix(deploy): sincroniza DATABASE_URL dos segredos do github para gcp",
    "use secret manager for GCP_SA_KEY": "fix(deploy): usa secret manager para GCP_SA_KEY evitando erros de sintaxe",
    "install requirements in deploy job": "fix(ci): instala dependências no job de deploy para sanity check",
    "add pip list debug": "ci: adiciona debug de pip list para investigar falta do flask",
    "implement lazy authentication": "fix(drive): implementa autenticação lazy para prevenir crash sem credenciais",
    "switch to Neon": "fix(database): muda para Neon e corrige mascaramento de senha na url",
    "implement zero-defect qa": "feat(qa): implementa camadas de qa zero-defect (hooks, docker-local, ci-verify)",
    "remove local secrets": "refactor: remove segredos locais, força env vars, adiciona workflow github",
    "Admin route 500": "fix: erro 500 na rota de admin, layout CSS e config do Cloud Tasks",
    "Secure Initial Release": "chore: Release Inicial Seguro (Histórico Limpo)"
}

def main():
    # Read from stdin for filter-branch
    content = sys.stdin.read()
    lines = content.splitlines()
    
    first_line = lines[0] if lines else ""
    
    # Check for match (naive substring check)
    new_msg = None
    for key, val in TRANSLATIONS.items():
        if key.lower() in first_line.lower():
            new_msg = val
            break
            
    if new_msg:
        # sys.stderr.write(f"Translating: {first_line[:20]}... -> {new_msg[:20]}...\n")
        print(new_msg)
        print("\nAlterações realizadas conforme diretrizes de internacionalização (PT-BR).")
    else:
        # Pass through unchanged
        print(content, end='')

if __name__ == "__main__":
    main()
