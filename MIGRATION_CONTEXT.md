# Documentação de Contexto para Migração de AI (Projeto MVP Inspeção Sanitária)

**Data:** 28/01/2026
**Objetivo:** Fornecer contexto completo para continuação do desenvolvimento em outra plataforma de AI (ex: Claude).

---

## 1. Visão Geral do Projeto
O projeto é um sistema de **Gestão de Inspeções Sanitárias** (MVP).
Ele permite o upload de relatórios/checklists (PDF/Imagens), processamento via OCR e IA (OpenAI), geração de Planos de Ação e fluxos de revisão para Gestores e Consultores.

### Stack Tecnológica
- **Backend:** Python (Flask)
- **Database:** PostgreSQL (SQLAlchemy ORM) via Cloud SQL (proxy local) ou Docker.
- **Frontend:** HTML5, Jinja2 Templates, Vanilla JS, Bootstrap/Tailwind (mistura de estilos legado/novo).
- **Processamento:** 
  - `Processamento Assíncrono`: Threads/Background tasks manuais (não usa Celery atualmente, mas usa conceito de `Jobs` no banco).
  - `AI/LLM`: OpenAI API (GPT-4o) para estruturação de dados.
  - `PDF`: WeasyPrint para geração de relatórios finais.
  - `Storage`: Google Drive API (para arquivos) e Banco de Dados (metadados).

---

## 2. Regras Críticas do Usuário (User Rules)
**Estas regras DEVEM ser seguidas rigorosamente pela nova IA:**

1.  **Segurança Extrema:** NUNCA comitar chaves, senhas ou URLs de banco sensíveis no GitHub.
2.  **Idioma:** TUDO em **Português** (Comentários, Commits, Explicações, Chat).
3.  **Ambiente:** Evitar comandos de "Production Mode" (Cloud Run, Vertex AI) a menos que explicitamente solicitado. Priorizar execução **LOCAL**.
4.  **Autonomia:**
    - "Always proceed": Não pedir permissão para editar arquivos ou rodar comandos seguros.
    - "Always confirm browser": Pode executar ações de navegador sem perguntar.
5.  **Configuração Cloud Run:** Se precisar buscar logs ou configs, usar:
    - Project: `projeto-poc-ap`
    - Region: `us-central1`
    - Service: `mvp-web`

---

## 3. Estado Atual e Mudanças Recentes (Últimas 24-48h)

### Backend (`src/`)
-   **Model `Job` (`src/models_db.py`):**
    -   Limpeza de colunas legadas (`summary_text`, `strengths_text`, etc.) removidas do DB.
    -   Campo `result_payload` (JSONB) agora é a fonte de verdade para resultados da IA (título, resumo, link output).
-   **Processador (`src/services/processor.py`):**
    -   Refatorado `_update_job_status` para persistir corretamente o `result_payload`.
    -   Corrigido bug que marcava inspeções como `REJECTED` devido a erros de atributo Pydantic (`.get()` vs `getattr`).
    -   Status do Job agora reflete corretamente falhas e sucessos.

### Frontend (`src/templates/`)
-   **Dashboard Admin (`src/templates/admin_dashboard.html`):**
    -   Adicionadas traduções faltantes no JS (`PENDING` -> PENDENTE, `SYNC_PROCESS` -> SINCRONIZAÇÃO, `CANCELED` -> CANCELADO).
    -   Corrigido erro JS `toggleCreateCompany is not defined`.
    -   Corrigida exibição vazia na coluna "Tipo".

### Fluxos de Negócio
-   **Revisão (Consultor/Gestor):**
    -   Lógica de "Parcialmente Conforme" ajustada para ser robusta (tratamento de strings case-insensitive).
    -   Geração de PDF agora inclui notas e status corretos.

---

## 4. Guia de Navegação para a Nova IA

### Arquivos Chave (Ler primeiro!)
1.  **`src/models_db.py`**: Definição do Schema do Banco. Entender `Job`, `Inspection`, `Company`.
2.  **`src/services/processor.py`**: Coração do sistema. Lógica de `process_single_file`, OCR, chamadas OpenAI e atualização de Jobs.
3.  **`src/app.py`**: Rotas principais e configuração do Flask.
4.  **`src/admin_routes.py`**: API do Dashboard Administrativo (monitoramento de jobs).
5.  **`task.md`** (na raiz ou artifacts): Lista de tarefas recente e status.

### Scripts Úteis (`scripts/`)
Criamos vários scripts para debug rápido (sem subir o servidor todo):
-   `scripts/debug_job_type.py`: Verificar status real no banco.
-   `scripts/debug_logs.py`: Ver logs de erro de um job específico.
-   `scripts/migration_cleanup_jobs.py`: Exemplo de migração manual (SQLAlchemy).

---

## 5. Pontos de Atenção (Falhas Comuns)
-   **Enum vs String:** O Python usa Enums (`JobStatus`), mas o Banco às vezes grava como string. O código tem tratativas (`try/except JobStatus(val)`), mas mantenha atenção nisso.
-   **Ambiente Local:** O projeto roda local com `python run.py`. Necessário `.env` configurado com `DATABASE_URL` e `OPENAI_API_KEY`.
-   **Google Drive:** A integração depende de credenciais (`client_secrets.json` / `token.json`). Se falhar, verificar permissões.

---

**Como "bootstrapar" a nova IA:**
> "Aqui está o arquivo `MIGRATION_CONTEXT.md` com todo o histórico técnico, regras de negócio e estado atual do projeto. Por favor, leia-o atentamente antes de começarmos a trabalhar na próxima tarefa."
