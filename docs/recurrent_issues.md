# Lista de Problemas Recorrentes & Regras de Ouro
> Esta lista deve ser verificada antes de qualquer entrega para evitar regressões.

## 1. Arquitetura "Zero Cost" & Cloud Run
- [x] **Limpeza de Imagens:** O script de deploy (.github/workflows/deploy.yml) DEVE conter o passo de limpeza mantendo apenas as **2 últimas** revisões/imagens.
    - *Erro Recorrente:* Deixar acumular imagens no Artifact Registry, estourando o free tier de 500MB.
    - *Validação:* Verificar presença de `tail -n +3` no script de cleanup.
- [x] **Sem Scheduler Pago:** Não usar Cloud Scheduler para poling frequente. Usar *Event-Driven* (Login do Admin, botões manuais) para sincronização.
    - *Validação:* Verificar se não há jobs cron criados via Terraform/gcloud que não sejam essenciais/gratuitos.

## 2. UX & Frontend (Fast & Frictionless)
- [x] **AJAX em Tudo:** Criação, Edição e Deleção (CRUD) devem ocorrer via AJAX/Fetch, sem recarregar a página inteira (exceto se necessário para consistência crítica, mas com feedback visual imediato).
    - *Erro Recorrente:* Forms fazendo POST padrão e recarregando tela (lento, "pisca" tela).
    - *Validação:* Verificar forms nos templates com handlers AJAX (`preventDefault`).

## 3. Segurança & Dados
- [ ] **Sem Secrets no Código:** NUNCA commitar chaves, senhas ou URLs de banco com credenciais.
    - *Erro Recorrente:* Hardcode de senhas para teste rápido.
    - *Validação:* Rodar script de busca por padrões de chaves antes do commit.

## 4. Padrões de Código
- [x] **Português Sempre:** Commits, comentários e logs devem estar em Português.
- [ ] **Flash Messages:** Garantir import correto de `get_flashed_messages` se usar Flask Flash.
    - *Erro Recorrente:* `NameError: name 'get_flashed_messages' is not defined`.
- [ ] **Auto-Patcher:** Scripts de migração (patcher.py) devem rodar no boot para garantir colunas novas no DB.
    - *Erro Recorrente:* `UndefinedColumn` após deploy.
