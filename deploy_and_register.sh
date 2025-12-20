#!/bin/bash
set -euo pipefail

# Configuration
SERVICE_NAME="mvp-web"
REGION="us-central1"
PROJECT_ID="projeto-poc-ap"
IMAGE="gcr.io/projeto-poc-ap/mvp-web"
PUBLIC_URL="https://mvp-web-aojigo3nta-uc.a.run.app"
# WEBHOOK_SECRET: Used for Drive notifications. In Prod, use Secret Manager.
WEBHOOK_SECRET="${DRIVE_WEBHOOK_TOKEN:-segredo-webhook-drive-dev}"

echo "🚀 Iniciando Deploy do Serviço com Configuração de Webhook..."

# --- NOVO: Verificação Pré-Deploy (Zero Defect) ---
echo "🔍 Executando scripts/sanity_check.py..."
# Tenta usar python3 do sistema ou venv se disponível
if [ -d ".venv" ]; then
    source .venv/bin/activate
    python3 scripts/sanity_check.py
    deactivate
else
    python3 scripts/sanity_check.py
fi

if [ $? -ne 0 ]; then
  echo "❌ Sanity Check FALHOU! Deploy abortado para evitar erros em produção."
  exit 1
fi
# ------------------------------------

# Constrói a imagem primeiro para garantir que o código esteja atualizado
echo "🔨 Construindo Imagem do Container..."
gcloud builds submit --tag "$IMAGE" --project "$PROJECT_ID" .


# Secret Manager helpers (mantém custo baixo e evita vazar credenciais em env vars)
ensure_secret () {
  local secret_name="$1"
  if ! gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "❌ Secret '$secret_name' não existe no Secret Manager (project=$PROJECT_ID)."
    echo "   Crie e adicione uma versão, por ex.:"
    echo "   gcloud secrets create $secret_name --replication-policy=automatic --project $PROJECT_ID"
    echo "   printf '%s' 'VALOR_AQUI' | gcloud secrets versions add $secret_name --data-file=- --project $PROJECT_ID"
    exit 1
  fi
}

update_secret_from_stdin () {
  local secret_name="$1"
  echo "🔐 Atualizando secret '$secret_name' (lendo do stdin)..."
  gcloud secrets versions add "$secret_name" --data-file=- --project "$PROJECT_ID" >/dev/null
  echo "✅ Secret atualizado: $secret_name"
}

update_secret_from_file () {
  local secret_name="$1"
  local file_path="$2"
  echo "🔐 Atualizando secret '$secret_name' (arquivo temporário)..."
  gcloud secrets versions add "$secret_name" --data-file="$file_path" --project "$PROJECT_ID" >/dev/null
  echo "✅ Secret atualizado: $secret_name"
}

test_database_url () {
  local url="$1"
  local py="./.venv/bin/python"
  if [[ ! -x "$py" ]]; then
    py="python3"
  fi

  DBURL="$url" "$py" - <<'PY'
import os
from urllib.parse import urlparse, parse_qs

try:
    import psycopg2
except Exception as e:
    raise SystemExit("❌ psycopg2 não disponível para teste local. (Ative o venv e instale deps.)") from e

u = os.environ["DBURL"]
p = urlparse(u)
qs = parse_qs(p.query)
sslmode = (qs.get("sslmode") or ["require"])[0]

try:
    conn = psycopg2.connect(
        host=p.hostname,
        port=p.port or 5432,
        user=p.username,
        password=p.password,
        dbname=(p.path or "/").lstrip("/") or "postgres",
        sslmode=sslmode,
        connect_timeout=5,
    )
    cur = conn.cursor()
    cur.execute("select 1")
    cur.close()
    conn.close()
    print("✅ Teste de conexão OK")
except Exception as e:
    msg = str(e).split("\n")[0]
    print(f"❌ Teste de conexão falhou: {msg}")
    raise
PY
}

# Opcional: atualiza DATABASE_URL de forma segura (sem imprimir no terminal).
# Uso recomendado:
#   UPDATE_DATABASE_URL_SECRET=1 bash deploy_and_register.sh
if [[ "${UPDATE_DATABASE_URL_SECRET:-}" == "1" ]]; then
  if ! gcloud secrets describe "DATABASE_URL" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create "DATABASE_URL" --replication-policy=automatic --project "$PROJECT_ID" >/dev/null
  fi

  echo "Cole aqui a DATABASE_URL completa (não será exibida de volta)."
  echo "Ex.: postgresql://user:password@params.neon.tech/dbname?sslmode=require"
  echo "Dica: Cole a Connection String completa do Neon."
  read -r -s DATABASE_URL_VALUE
  echo
  tmp_file="$(mktemp)"
  trap 'rm -f "$tmp_file"' EXIT

  DATABASE_URL_VALUE="$DATABASE_URL_VALUE" OUT_FILE="$tmp_file" python3 - <<'PY'
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import os, sys

raw = os.environ.get("DATABASE_URL_VALUE", "").strip()
if not raw:
    print("❌ DATABASE_URL vazia.")
    sys.exit(1)

if raw.count("postgresql://") > 1 or raw.count("postgres://") > 1:
    print("❌ DATABASE_URL inválida: parece conter mais de uma URL colada (duplicada).")
    sys.exit(1)

p = urlparse(raw)
if p.scheme not in ("postgresql", "postgres"):
    print(f"❌ DATABASE_URL inválida: scheme inesperado ({p.scheme}).")
    sys.exit(1)
if not p.hostname or not p.port:
    print("❌ DATABASE_URL inválida: host/porta ausentes.")
    sys.exit(1)
if not p.username:
    print("❌ DATABASE_URL inválida: usuário ausente.")
    sys.exit(1)
db = (p.path or "").lstrip("/")
if not db or "postgresql://" in db or "postgres://" in db:
    print("❌ DATABASE_URL inválida: nome do banco está mal formatado.")
    sys.exit(1)

host = (p.hostname or "").lower()

# (Supabase checks removed)

query = dict(parse_qsl(p.query, keep_blank_values=True))
# Ensure sslmode for any cloud provider if appropriate, or rely on URL params
if "sslmode" not in query:
    query["sslmode"] = "require"

normalized = urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(query), p.fragment))
out_file = os.environ.get("OUT_FILE")
if not out_file:
    print("❌ OUT_FILE ausente.")
    sys.exit(1)
with open(out_file, "w", encoding="utf-8") as f:
    f.write(normalized)

print(f"✅ Validado: host={p.hostname} port={p.port} user={p.username} db={db} sslmode={query.get('sslmode')}")
PY
  update_secret_from_file "DATABASE_URL" "$tmp_file"

  # Se solicitado, testa a conexão imediatamente após atualizar o secret.
  # Isso evita subir revisão quebrada por senha/host incorreto.
  if [[ "${TEST_DATABASE_URL:-}" == "1" ]]; then
    echo "🧪 Testando conexão com o banco usando a DATABASE_URL informada..."
    normalized_dburl="$(cat "$tmp_file")"
    test_database_url "$normalized_dburl"
    echo "✅ Conexão OK. Prosseguindo com o deploy..."
  fi
fi

ensure_secret "DATABASE_URL"
ensure_secret "OPENAI_API_KEY"
# WHATSAPP_TOKEN é opcional (fluxo de WhatsApp pode ser desativado no MVP)

# Opcional: smoke test da DATABASE_URL antes do deploy (evita subir revisão quebrada).
# Uso:
#   TEST_DATABASE_URL=1 bash deploy_and_register.sh
if [[ "${TEST_DATABASE_URL:-}" == "1" ]]; then
  echo "🧪 Testando conexão com o banco usando o secret DATABASE_URL..."
  dburl="$(gcloud secrets versions access latest --secret=DATABASE_URL --project "$PROJECT_ID")"
  test_database_url "$dburl"
fi

# Deploy and set environment variables
# Nota: preferimos manter segredos via Secret Manager (mais seguro que env var em texto).
# Determina segredos opcionais para incluir no deploy consolidado
SECRETS_LIST="DATABASE_URL=DATABASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest"

if gcloud secrets describe "WHATSAPP_TOKEN" --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRETS_LIST="${SECRETS_LIST},WHATSAPP_TOKEN=WHATSAPP_TOKEN:latest"
fi

if gcloud secrets describe "GOOGLE_DRIVE_IMPERSONATE_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRETS_LIST="${SECRETS_LIST},GOOGLE_DRIVE_IMPERSONATE_EMAIL=GOOGLE_DRIVE_IMPERSONATE_EMAIL:latest"
fi

# SYNC DATABASE_URL: Garante que o valor do GitHub Secret sobrescreva o Secret Manager (Fonte da Verdade)
if [ -n "${DATABASE_URL:-}" ]; then
  if ! gcloud secrets describe "DATABASE_URL" --project "$PROJECT_ID" >/dev/null 2>&1; then
     gcloud secrets create "DATABASE_URL" --replication-policy=automatic --project "$PROJECT_ID"
  fi
  printf "%s" "$DATABASE_URL" | gcloud secrets versions add "DATABASE_URL" --data-file=- --project "$PROJECT_ID" >/dev/null
  echo "✅ Secret DATABASE_URL sincronizado do GitHub para Secret Manager."
fi

if [ -n "${GCP_SA_KEY:-}" ]; then
  # Se GCP_SA_KEY foi passada (via CI), salve no Secret Manager para evitar problemas de parsing no deploy
  # e para garantir segurança.
  if ! gcloud secrets describe "GCP_SA_KEY" --project "$PROJECT_ID" >/dev/null 2>&1; then
     gcloud secrets create "GCP_SA_KEY" --replication-policy=automatic --project "$PROJECT_ID"
  fi
  echo "$GCP_SA_KEY" | gcloud secrets versions add "GCP_SA_KEY" --data-file=- --project "$PROJECT_ID" >/dev/null
  echo "✅ Secret GCP_SA_KEY atualizado com sucesso."
  SECRETS_LIST="${SECRETS_LIST},GCP_SA_KEY=GCP_SA_KEY:latest"
  SECRETS_LIST="${SECRETS_LIST},GCP_SA_KEY=GCP_SA_KEY:latest"
fi

# SYNC AWS SECRETS: AWS_ACCESS_KEY_ID
if [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
  if ! gcloud secrets describe "AWS_ACCESS_KEY_ID" --project "$PROJECT_ID" >/dev/null 2>&1; then
     gcloud secrets create "AWS_ACCESS_KEY_ID" --replication-policy=automatic --project "$PROJECT_ID"
  fi
  printf "%s" "$AWS_ACCESS_KEY_ID" | gcloud secrets versions add "AWS_ACCESS_KEY_ID" --data-file=- --project "$PROJECT_ID" >/dev/null
  echo "✅ Secret AWS_ACCESS_KEY_ID sincronizado."
fi

# SYNC AWS SECRETS: AWS_SECRET_ACCESS_KEY
if [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  if ! gcloud secrets describe "AWS_SECRET_ACCESS_KEY" --project "$PROJECT_ID" >/dev/null 2>&1; then
     gcloud secrets create "AWS_SECRET_ACCESS_KEY" --replication-policy=automatic --project "$PROJECT_ID"
  fi
  printf "%s" "$AWS_SECRET_ACCESS_KEY" | gcloud secrets versions add "AWS_SECRET_ACCESS_KEY" --data-file=- --project "$PROJECT_ID" >/dev/null
  echo "✅ Secret AWS_SECRET_ACCESS_KEY sincronizado."
fi

# Add AWS Secrets to Deploy List if they exist
if gcloud secrets describe "AWS_ACCESS_KEY_ID" --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRETS_LIST="${SECRETS_LIST},AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID:latest"
fi
if gcloud secrets describe "AWS_SECRET_ACCESS_KEY" --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRETS_LIST="${SECRETS_LIST},AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY:latest"
fi

# ADD AWS_SES_SENDER (Optional)
if [ -n "${AWS_SES_SENDER:-}" ]; then
  # Passar como Env Var direta é mais simples, já que não é secreto (é um email)
  # Mas para consistência, podemos passar via --set-env-vars no comando final
  echo "📧 Configurando Remetente de Email: $AWS_SES_SENDER"
fi

# Deploy Consolidado (Evita sobrescrever variáveis entre comandos)
echo "🚀 Executando deploy consolidado..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT_ID \
  --max-instances 2 \
  --concurrency 20 \
  --set-env-vars "APP_PUBLIC_URL=$PUBLIC_URL" \
  --set-env-vars "DRIVE_WEBHOOK_TOKEN=$WEBHOOK_SECRET" \
  --set-env-vars "DB_POOL_SIZE=2,DB_MAX_OVERFLOW=3,DB_POOL_TIMEOUT=30,DB_POOL_RECYCLE=1800" \
  --set-env-vars "FOLDER_ID_01_ENTRADA_RELATORIOS=${FOLDER_ID_01_ENTRADA_RELATORIOS:?Faltando Env Var FOLDER_ID_01}" \
  --set-env-vars "FOLDER_ID_02_PLANOS_GERADOS=${FOLDER_ID_02_PLANOS_GERADOS:?Faltando Env Var FOLDER_ID_02}" \
  --set-env-vars "FOLDER_ID_03_PROCESSADOS_BACKUP=${FOLDER_ID_03_PROCESSADOS_BACKUP:?Faltando Env Var FOLDER_ID_03}" \
  --set-env-vars "FOLDER_ID_99_ERROS=${FOLDER_ID_99_ERROS:?Faltando Env Var FOLDER_ID_99}" \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
  --set-env-vars "GCP_LOCATION=$REGION" \
  --set-env-vars "AWS_SES_SENDER=${AWS_SES_SENDER:-noreply@inspetorai.com}" \
  --set-secrets "$SECRETS_LIST"

echo "✅ Deploy concluído com sucesso."

# --------------------------------------------------------------------------------
# Pós-processamento (Opcional: Registro de Webhook)
# --------------------------------------------------------------------------------
if [ -n "$PUBLIC_URL" ]; then
  echo "🔗 Registrando Webhook do Drive..."
  curl -X POST "${PUBLIC_URL}/api/webhook/renew" \
       -H "Content-Type: application/json" \
       -v || echo "⚠️ Falha ao registrar webhook (ignorado)"
fi

echo "🎉 Tudo pronto! O serviço está em: $PUBLIC_URL"
