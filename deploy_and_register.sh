#!/bin/bash
set -euo pipefail

# Configuration
SERVICE_NAME="mvp-web"
REGION="${GCP_LOCATION:-us-central1}"
PROJECT_ID="${GCP_PROJECT_ID:-projeto-poc-ap}"
IMAGE="gcr.io/projeto-poc-ap/mvp-web"
PUBLIC_URL="${APP_PUBLIC_URL:-https://mvp-web-aojigo3nta-uc.a.run.app}"
# WEBHOOK_SECRET: Used for Drive notifications. In Prod, use Secret Manager.
WEBHOOK_SECRET="${DRIVE_WEBHOOK_TOKEN:-segredo-webhook-drive-dev}"

echo "🚀 Iniciando Deploy do Serviço com Configuração de Webhook..."

# --- NOVO: Verificação Pré-Deploy (Zero Defect) ---
if [ "${SKIP_SANITY_CHECK:-0}" != "1" ]; then
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
else
    echo "⏩ Pulanado Sanity Check (SKIP_SANITY_CHECK=1)..."
fi
# ------------------------------------

# Constrói a imagem primeiro para garantir que o código esteja atualizado
# Constrói a imagem com Cache (Kaniko) via cloudbuild.yaml
echo "🔨 Construindo Imagem do Container (Otimizado with Kaniko)..."
gcloud builds submit --config cloudbuild.yaml --project "$PROJECT_ID" .


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

audit_secret () {
  local name="$1"
  local val="${!name:-}"
  if [ -z "$val" ]; then
    echo "⚠️  VARÍAVEL AUSENTE NO GITHUB: $name"
  else
    local len=${#val}
    local start="${val:0:6}"
    local end="${val: -4}"
    echo "🔍 AUDIT: $name [Size: $len] | Prefix: $start... | Suffix: ...$end"
  fi
}

trim_var () {
  local var_name="$1"
  local val="${!var_name:-}"
  # Remove leading/trailing whitespace and quotes
  val=$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
  eval "$var_name=\$val"
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

# Atualiza OPENAI_API_KEY se solicitado
# Uso: update_openai_key=1 bash deploy_and_register.sh
if [[ "${update_openai_key:-}" == "1" ]] || [[ "${UPDATE_OPENAI_KEY:-}" == "1" ]]; then
  echo "🔑 Atualização da API Key da OpenAI solicitada."
  echo "Por favor, cole a nova chave (começa com sk-...):"
  read -r -s NEW_OPENAI_KEY
  echo

  # Remove espaços em branco
  NEW_OPENAI_KEY=$(echo "$NEW_OPENAI_KEY" | xargs)

  if [[ "$NEW_OPENAI_KEY" != sk-* ]]; then
    echo "⚠️  Aviso: A chave colada não começa com 'sk-'. Verifique se copiou corretamente."
  fi

  if [ -z "$NEW_OPENAI_KEY" ]; then
     echo "❌ Chave vazia. Abortando atualização."
     exit 1
  fi
  
  # Usa helper se disponível ou comando direto
  printf '%s' "$NEW_OPENAI_KEY" | gcloud secrets versions add "OPENAI_API_KEY" --data-file=- --project "$PROJECT_ID"
  echo "✅ Secret OPENAI_API_KEY atualizado com sucesso."
fi

ensure_secret "DATABASE_URL"
ensure_secret "OPENAI_API_KEY"
# WHATSAPP_TOKEN é opcional (fluxo de WhatsApp pode ser desativado no MVP)

# Initialize SECRETS_LIST
SECRETS_LIST=""

# moved to after SECRETS_LIST init

# Opcional: smoke test da DATABASE_URL antes do deploy (evita subir revisão quebrada).
# Uso:
#   TEST_DATABASE_URL=1 bash deploy_and_register.sh
if [[ "${TEST_DATABASE_URL:-}" == "1" ]]; then
  echo "🧪 Testando conexão com o banco usando o secret DATABASE_URL..."
  dburl="$(gcloud secrets versions access latest --secret=DATABASE_URL --project "$PROJECT_ID")"
  test_database_url "$dburl"
fi

# Determina segredos opcionais para incluir no deploy consolidado
# ALIASES para FOLDER_IDs
FOLDER_ID_01_ENTRADA_RELATORIOS="${FOLDER_ID_01_ENTRADA_RELATORIOS:-${FOLDER_ID_01:-}}"
FOLDER_ID_02_PLANOS_GERADOS="${FOLDER_ID_02_PLANOS_GERADOS:-${FOLDER_ID_02:-}}"
FOLDER_ID_03_PROCESSADOS_BACKUP="${FOLDER_ID_03_PROCESSADOS_BACKUP:-${FOLDER_ID_03:-}}"
FOLDER_ID_99_ERROS="${FOLDER_ID_99_ERROS:-${FOLDER_ID_99:-}}"

# CLEANUP SECRETS (TRIM)
trim_var "OPENAI_API_KEY"
trim_var "DATABASE_URL"
trim_var "SECRET_KEY"
trim_var "WHATSAPP_TOKEN"

# --- TESTE LIVE OPENAI (Evita subir chave inválida) ---
# if [ "${SKIP_SANITY_CHECK:-0}" != "1" ] && [ -n "$OPENAI_API_KEY" ]; then
#   echo "🧪 Testando validade da OPENAI_API_KEY via API..."
#   HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models \
#     -H "Authorization: Bearer $OPENAI_API_KEY")
#   if [ "$HTTP_CODE" -eq 401 ]; then
#     echo "❌ FALHA CRÍTICA: A chave OpenAI no GitHub Secrets é INVÁLIDA (401 Unauthorized)."
#     echo "   Por favor, gere uma nova chave na OpenAI e atualize o GitHub Secret."
#     # audit_secret "OPENAI_API_KEY" # Já feito na auditoria
#     exit 1
#   elif [ "$HTTP_CODE" -eq 200 ]; then
#     echo "✅ Conexão OpenAI confirmada."
#   else
#     echo "⚠️  OpenAI retornou status $HTTP_CODE (pode ser problema de rede ou cota, mas auth passou)."
#   fi
# fi

# Validação final de pastas críticas (COMENTADO PARA DEPLOY LOCAL)
# if [ -z "$FOLDER_ID_01_ENTRADA_RELATORIOS" ] || [ -z "$FOLDER_ID_02_PLANOS_GERADOS" ]; then
#   echo "❌ ERRO: IDs de pastas críticas (01 ou 02) estão vazios após mapeamento de aliases!"
#   echo "   Verifique se as pastas FOLDER_ID_01 e FOLDER_ID_02 estão no GitHub Secrets. (IGNORADO LOCALMENTE)"
#   # exit 1 
# fi

SECRETS_LIST="DATABASE_URL=DATABASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest"

if gcloud secrets describe "WHATSAPP_TOKEN" --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRETS_LIST="${SECRETS_LIST},WHATSAPP_TOKEN=WHATSAPP_TOKEN:latest"
fi

# IMPERSONATION DISABLED: User is on consumer Gmail (@gmail.com) which does not support Domain-Wide Delegation.
# We must use the Service Account directly and share folders with it.
# if gcloud secrets describe "GOOGLE_DRIVE_IMPERSONATE_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
#   SECRETS_LIST="${SECRETS_LIST},GOOGLE_DRIVE_IMPERSONATE_EMAIL=GOOGLE_DRIVE_IMPERSONATE_EMAIL:latest"
# fi
 
# NEW: OAuth Token for Drive (Storage Quota Fix) - Moved here to prevent overwrite
if gcloud secrets describe "GCP_OAUTH_TOKEN" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "🔑 Secret GCP_OAUTH_TOKEN encontrado! Injetando no deploy..."
    SECRETS_LIST="${SECRETS_LIST},GCP_OAUTH_TOKEN=GCP_OAUTH_TOKEN:latest"
else
    echo "⚠️ GCP_OAUTH_TOKEN não encontrado (Usando Service Account Fallback)"
fi



# Folder IDs (Still passed as Env Vars for simplicity, or could be Secrets)
# For now, we kept them as Env Vars in the previous logic, sticking to that.

# Optional AWS Keys - Blindly add them if we expect them, or strictly check env var presence?
# If we want to be safe without gcloud calls, we can conditionally add them if the ENV VAR is present in the build environment
if [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
  SECRETS_LIST="${SECRETS_LIST},AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID:latest"
fi
if [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  SECRETS_LIST="${SECRETS_LIST},AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY:latest"
fi
# GCP SA KEY
if [ -n "${GCP_SA_KEY:-}" ]; then
  SECRETS_LIST="${SECRETS_LIST},GCP_SA_KEY=GCP_SA_KEY:latest"
fi
# Drive Webhook Token (Pass as Env Var since it might not exist in Secret Manager)
# SECRETS_LIST="${SECRETS_LIST},DRIVE_WEBHOOK_TOKEN=DRIVE_WEBHOOK_TOKEN:latest"


echo "🚀 Executando deploy consolidado..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT_ID \
  --max-instances 2 \
  --concurrency 20 \
  --allow-unauthenticated \
  --set-env-vars "WEBHOOK_SECRET_TOKEN=$WEBHOOK_SECRET" \
  --set-env-vars "DB_POOL_SIZE=2,DB_MAX_OVERFLOW=3,DB_POOL_TIMEOUT=30,DB_POOL_RECYCLE=1800" \
  --set-env-vars "FOLDER_ID_01_ENTRADA_RELATORIOS=${FOLDER_ID_01_ENTRADA_RELATORIOS}" \
  --set-env-vars "FOLDER_ID_02_PLANOS_GERADOS=${FOLDER_ID_02_PLANOS_GERADOS}" \
  --set-env-vars "FOLDER_ID_03_PROCESSADOS_BACKUP=${FOLDER_ID_03_PROCESSADOS_BACKUP}" \
  --set-env-vars "FOLDER_ID_99_ERROS=${FOLDER_ID_99_ERROS}" \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
  --set-env-vars "GCP_LOCATION=$REGION" \
  --set-env-vars "AWS_SES_SENDER=${AWS_SES_SENDER:-noreply@inspetorai.com}" \
  --set-env-vars "WHATSAPP_PHONE_ID=${WHATSAPP_PHONE_ID:-}" \
  --set-env-vars "WHATSAPP_DESTINATION_PHONE=${WHATSAPP_DESTINATION_PHONE:-}" \
  --set-secrets "$SECRETS_LIST"

echo "✅ Deploy do serviço web concluído."

echo "🚀 Executando deploy do WORKER como Cloud Run JOB (mvp-worker)..."
# Usamos 'deploy' que cria se não existir ou atualiza se existir
gcloud run jobs deploy mvp-worker \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT_ID \
  --command "python" \
  --args="-m,src.main,--once" \
  --set-env-vars "WEBHOOK_SECRET_TOKEN=$WEBHOOK_SECRET" \
  --set-env-vars "APP_PUBLIC_URL=$PUBLIC_URL" \
  --set-env-vars "DB_POOL_SIZE=2,DB_MAX_OVERFLOW=3,DB_POOL_TIMEOUT=30,DB_POOL_RECYCLE=1800" \
  --set-env-vars "FOLDER_ID_01_ENTRADA_RELATORIOS=${FOLDER_ID_01_ENTRADA_RELATORIOS}" \
  --set-env-vars "FOLDER_ID_02_PLANOS_GERADOS=${FOLDER_ID_02_PLANOS_GERADOS}" \
  --set-env-vars "FOLDER_ID_03_PROCESSADOS_BACKUP=${FOLDER_ID_03_PROCESSADOS_BACKUP}" \
  --set-env-vars "FOLDER_ID_99_ERROS=${FOLDER_ID_99_ERROS}" \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
  --set-env-vars "GCP_LOCATION=$REGION" \
  --set-env-vars "AWS_SES_SENDER=${AWS_SES_SENDER:-noreply@inspetorai.com}" \
  --set-env-vars "WHATSAPP_PHONE_ID=${WHATSAPP_PHONE_ID:-}" \
  --set-env-vars "WHATSAPP_DESTINATION_PHONE=${WHATSAPP_DESTINATION_PHONE:-}" \
  --set-secrets "$SECRETS_LIST"

echo "✅ Deploy do worker (Job) concluído com sucesso."

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
