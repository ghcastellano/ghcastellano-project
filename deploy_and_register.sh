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

# --- NOVO: Verificação Pré-Deploy ---
echo "🔍 Executando scripts/verify_deploy.py..."
python3 scripts/verify_deploy.py
if [ $? -ne 0 ]; then
  echo "❌ Verificação Pré-Deploy falhou! Deploy cancelado por segurança."
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
  echo "Ex.: postgresql://postgres.<ref>:*****@aws-0-<region>.pooler.supabase.com:5432/postgres"
  echo "Dica: a senha correta é a 'Database password' (Reset database password no Supabase), não é anon/service key."
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
is_pooler = "pooler.supabase.com" in host
if is_pooler and "." not in (p.username or ""):
    print("❌ Para o Supabase Pooler, o usuário precisa ser do tipo 'postgres.<project-ref>'.")
    sys.exit(1)

query = dict(parse_qsl(p.query, keep_blank_values=True))
if (host.endswith("supabase.co") or host.endswith("supabase.com")) and "sslmode" not in query:
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
  --set-env-vars FOLDER_ID_01_ENTRADA_RELATORIOS="1nHUNMLNdETy1Wkhu1i5ZSD6fh72fqbTW" \
  --set-env-vars FOLDER_ID_02_PLANOS_GERADOS="1nBBlpVmTSPdpMZGZA1HjrRmi-_W30qoM" \
  --set-env-vars FOLDER_ID_03_PROCESSADOS_BACKUP="1kgNrQxQNAp5h_rG3xYzD-a5v38zYvfUw" \
  --set-env-vars FOLDER_ID_99_ERROS="1KHlP7dbeyX8_hUF5Y8mooSu7jnB4ZZzK" \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
  --set-env-vars "GCP_LOCATION=$REGION" \
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
