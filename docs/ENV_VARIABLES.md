# Variáveis de Ambiente

## Obrigatórias

### Banco de Dados
| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | URL de conexão PostgreSQL | `postgresql://user:pass@host/db` |

### Segurança
| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `SECRET_KEY` | Chave secreta Flask para sessões | `sua-chave-secreta-aqui` |

### OpenAI
| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `OPENAI_API_KEY` | API Key da OpenAI | `sk-proj-...` |

## Google Drive

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `GCP_SA_KEY` | Service Account JSON (completo) | `{"type":"service_account",...}` |
| `GCP_OAUTH_TOKEN` | OAuth Token (alternativo ao SA) | `{"refresh_token":"..."}` |
| `GDRIVE_ROOT_FOLDER_ID` | ID da pasta raiz no Drive | `1p3lZ4Uj...` |
| `FOLDER_ID_01_ENTRADA_RELATORIOS` | Pasta de entrada | ID do Drive |
| `FOLDER_ID_02_PLANOS_GERADOS` | Pasta de saída | ID do Drive |
| `FOLDER_ID_03_PROCESSADOS_BACKUP` | Pasta de backup | ID do Drive |
| `FOLDER_ID_99_ERROS` | Pasta de erros | ID do Drive |

## Email (SMTP)

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `SMTP_EMAIL` | Email do remetente | `app@gmail.com` |
| `SMTP_PASSWORD` | App Password do Gmail | `xxxx xxxx xxxx xxxx` |
| `SMTP_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `SMTP_PORT` | Porta SMTP | `587` |

## WhatsApp Business API

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `WHATSAPP_TOKEN` | Bearer Token Meta | `EAAx...` |
| `WHATSAPP_PHONE_ID` | Phone Number ID | `123456789` |
| `WHATSAPP_DESTINATION_PHONE` | Telefone padrão | `5511999999999` |

## Google Cloud

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `GCP_PROJECT_ID` | ID do projeto GCP | `my-project` |
| `GCP_LOCATION` | Região do Cloud Run | `us-central1` |
| `GCS_BUCKET_NAME` | Bucket do Cloud Storage | `my-bucket` |

## Desenvolvimento

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `FLASK_ENV` | Ambiente Flask | `development` |
| `FLASK_DEBUG` | Modo debug | `true` / `false` |
| `TESTING` | Modo de teste | `true` / `false` |

## Variáveis Automáticas (Cloud Run)

| Variável | Descrição |
|----------|-----------|
| `K_SERVICE` | Nome do serviço (definida pelo Cloud Run) |
| `PORT` | Porta do servidor (padrão: 8080) |

## Configuração Local

1. Copie `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```

2. Preencha as variáveis obrigatórias

3. Para desenvolvimento, as variáveis podem ser definidas no arquivo `.env`

## Configuração em Produção (GitHub Secrets)

As credenciais são armazenadas no GitHub Secrets e injetadas durante o deploy via Cloud Build.

**Secrets Configurados:**
- `DATABASE_URL`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- `GCP_SA_KEY`
- `SMTP_PASSWORD`
- `WHATSAPP_TOKEN`

## Notas de Segurança

- **Nunca commite** o arquivo `.env` no repositório
- Use **GitHub Secrets** para produção
- Rotacione credenciais periodicamente
- API keys não são logadas (sanitização implementada)
