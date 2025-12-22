#!/bin/bash
# scripts/verify_deploy.sh
# Verifies if the Cloud Run service is healthy and checks for recent errors in logs.

SERVICE_NAME="mvp-web"
PROJECT_ID="projeto-poc-ap"
REGION="us-central1"

echo "🔍 Iniciando Verificação Pós-Deploy..."

# 1. Check Service Status & URL
echo "📡 Verificando Status do Serviço..."
SERVICE_INFO=$(gcloud run services describe $SERVICE_NAME --region $REGION --project $PROJECT_ID --format="json")
URL=$(echo $SERVICE_INFO | jq -r .status.url)
LATEST_READY=$(echo $SERVICE_INFO | jq -r .status.latestReadyRevisionName)
LATEST_CREATED=$(echo $SERVICE_INFO | jq -r .status.latestCreatedRevisionName)

echo "   URL: $URL"
echo "   Revision Created: $LATEST_CREATED"
echo "   Revision Ready:   $LATEST_READY"

if [ "$LATEST_READY" != "$LATEST_CREATED" ]; then
    echo "❌ FALHA: A revisão mais recente ($LATEST_CREATED) NÃO está pronta."
    echo "   Isso indica falha na inicialização do container."
    exit 1
fi

# 2. Check Recent Logs (Last 2 minutes) for Errors
echo "📋 Analisando Logs Recentes (2 min)..."
LOG_FILTER="resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=ERROR AND timestamp>=\"$(date -u -v-2M +%Y-%m-%dT%H:%M:%SZ)\""

ERROR_LOGS=$(gcloud logging read "$LOG_FILTER" --limit 5 --project $PROJECT_ID --format="value(textPayload, jsonPayload.message)")

if [ ! -z "$ERROR_LOGS" ]; then
    echo "❌ ERROS ENCONTRADOS NOS LOGS RECENTES:"
    echo "$ERROR_LOGS"
    echo "----------------------------------------"
    echo "⚠️ O deploy pode ter completado, mas a aplicação está gerando erros."
    exit 1
else
    echo "✅ Nenhum erro recente encontrado nos logs."
fi

echo "✅ Verificação Concluída: Serviço Saudável."
exit 0
