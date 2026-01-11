# Diretrizes do Projeto (Project Guidelines) 🛡️🇧🇷

Este documento estabelece as regras de ouro para o desenvolvimento deste projeto. **Qualquer agente ou desenvolvedor deve seguir estas regras rigorosamente.**

## 1. Idioma: Português (PT-BR) 🇧🇷
*   **TUDO deve ser em Português:**
    *   Código (comentários, docstrings).
    *   Commits (mensagens de commit).
    *   Documentação (arquivos .md, planos).
    *   Interação (chat, issues).
*   *Exceção:* Nomes de variáveis/funções em inglês são aceitáveis se for o padrão da linguagem (ex: python), mas comentários explicativos devem ser em PT-BR.

## 2. Arquitetura Zero Cost (Custo Zero) 💸
*   **Serverless First:** O projeto deve rodar em infraestrutura que escala a zero (Cloud Run).
*   **Zero Idle Traffic:**
    *   🚫 **Proibido:** `setInterval`, `polling` ou qualquer script que gere tráfego contínuo sem ação do usuário.
    *   ✅ **Permitido:** Botões de "Atualizar", Webhooks, Lógica "On-Demand".
*   **Free Tier Only:**
    *   Use cotas gratuitas (Drive pessoal 15GB, Cloud Build daily limit).
    *   Evite serviços com custo fixo (ex: Cloud SQL, Load Balancers pagos) a menos que explicitamente autorizado.

## 4. Gestão de Segredos e Onboarding 🔑
Este projeto usa uma estratégia híbrida para manter custo Zero e Alta Segurança:

*   **PRODUÇÃO (Cloud Run):** 
    *   As chaves ficam no **GitHub Secrets**.
    *   O workflow `.github/workflows/deploy.yml` injeta elas como variáveis de ambiente na hora do deploy.
    *   *NUNCA* use o Google Secret Manager (Custo $).

*   **LOCAL (Desenvolvimento):**
    *   As chaves ficam no arquivo `.env` (gitignored).
    *   **Novos Devs/Agentes:**
        1.  Copiem `.env.example` para `.env`.
        2.  Rodem `python scripts/setup_secrets.py` para validar.
        3.  Preencham as chaves manualmente (pegar com admin).

*   **Adaptação Automática:**
    *   O script `setup_secrets.py` deve ser rodado ao iniciar o ambiente para garantir que tudo está no lugar.

## 4. commits
*   Sempre use [Conventional Commits](https://www.conventionalcommits.org/pt-br) em Português.
    *   `feat: ...` -> `feat: adiciona login...`
    *   `fix: ...` -> `fix: corrige erro 500...`

---
*Este arquivo deve ser lido no início de cada sessão para garantir alinhamento.*
