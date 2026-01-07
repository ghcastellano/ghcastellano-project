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


# Deploy do Serviço
echo "🚀 Executando deploy consolidado (Usando Variáveis de Ambiente - GitHub Secrets Mode)..."

# Garante que as vars críticas existam (vêm do GitHub Actions ou .env local)
if [ -z "${DATABASE_URL:-}" ]; then echo "❌ DATABASE_URL não definida!"; exit 1; fi
if [ -z "${OPENAI_API_KEY:-}" ]; then echo "❌ OPENAI_API_KEY não definida!"; exit 1; fi
if [ -z "${SECRET_KEY:-}" ]; then echo "❌ SECRET_KEY não definida!"; exit 1; fi

gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT_ID \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 40 \
  --memory 512Mi \
  --cpu 1 \
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
  --set-env-vars "DATABASE_URL=${DATABASE_URL}" \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY}" \
  --set-env-vars "SECRET_KEY=${SECRET_KEY}" \
  --set-env-vars "WHATSAPP_TOKEN=${WHATSAPP_TOKEN:-}" \
  --set-env-vars "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}" \
  --set-env-vars "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}"

echo "✅ Deploy do serviço web concluído."



# --------------------------------------------------------------------------------
# Pós-processamento (Opcional: Registro de Webhook)
# --------------------------------------------------------------------------------
if [ -n "$PUBLIC_URL" ]; then
  echo "🔗 Registrando Webhook do Drive..."
  curl -X POST "${PUBLIC_URL}/api/webhook/renew" \
       -H "Content-Type: application/json" \
       -v || echo "⚠️ Falha ao registrar webhook (ignorado)"
fi

# NOVO: Otimização de Custos Automática
echo "--------------------------------------------------------"
echo "💰 Executando limpeza automática de custos (Keep 2)..."
chmod +x scripts/optimize_costs.sh
./scripts/optimize_costs.sh
echo "--------------------------------------------------------"

echo "🎉 Tudo pronto! O serviço está em: $PUBLIC_URL"
