# Configuração de CI/CD (GitHub Actions)

O pipeline de deploy foi configurado para **Produção com Zero Cost Architecture**.
Sempre que houver um `push` para a branch `main`:
1.  Testes automáticos podem ser rodados (se configurados).
2.  Build e Push da Imagem Docker.
3.  Deploy para o Cloud Run.
4.  **Limpeza Automática**: O script remove versões e imagens antigas, mantendo apenas as 2 mais recentes.

## 🔑 Secrets Necessários (GitHub)

Para que o deploy funcione, você precisa cadastrar as seguintes **Repository Secrets** no GitHub (`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`):

| Nome da Secret | Descrição | Exemplo / Onde pegar |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | Conteúdo do JSON da Service Account do Google Cloud | `credentials.json` (Tem que ter permissão de Cloud Run Admin, Storage Admin e Service Account User) |
| `DATABASE_URL` | String de conexão do Banco de Dados (Neon/Supabase) | `postgresql://user:pass@host/db?sslmode=require` |
| `OPENAI_API_KEY` | Chave da API da OpenAI | `sk-...` |
| `AWS_ACCESS_KEY_ID` | ID da chave de acesso AWS (para S3/SES) | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | Chave secreta AWS | `wJalr...` |
| `FLASK_SECRET_KEY` | Chave aleatória para segurança de sessão do Flask | Gere com `openssl rand -hex 32` |

## ⚙️ Variáveis Configuradas (Hardcoded no YAML)

As seguintes variáveis de ambiente foram fixadas no arquivo `deploy.yml` pois são configurações de infraestrutura estáveis:
- `FOLDER_ID_01_ENTRADA_RELATORIOS`: `1F8NcC0aR9MQnHDCEJdbx_BuanK8rg08B`
- `FOLDER_ID_02_PLANOS_GERADOS`: `15Cip-MIZS8zWaXZen4n0jN8NWPo0LedP`
- `FOLDER_ID_03_PROCESSADOS_BACKUP`: `1mGSz1GqyZRgninE8oC5LvBKfHptJ2qh1`
- `FOLDER_ID_99_ERROS`: `15B46XHBTGWWojwGHbMzp-Ic7kFJOwYYe`
- `AWS_SES_SENDER`: `noreply@seudominio.com`

## 🚀 Como fazer o Deploy

1. Garanta que as secrets estão cadastradas no GitHub.
2. Faça push para a main:
   ```bash
   git add .
   git commit -m "Deploy production"
   git push origin main
   ```
3. Acompanhe a aba "Actions" no GitHub para ver o progresso.
