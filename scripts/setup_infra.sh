#!/bin/bash
set -e

# Config
PROJECT_ID="${GCP_PROJECT_ID:-projeto-poc-ap}"
LOCATION="${GCP_LOCATION:-us-central1}"
QUEUE_NAME="mvp-tasks"
APP_URL="${APP_PUBLIC_URL:-https://mvp-web-aojigo3nta-uc.a.run.app}"

echo "🚀 Iniciando Configuração de Infraestrutura Pós-Deploy..."

# 1. Cloud Tasks Queue
echo "Checking Cloud Tasks Queue: $QUEUE_NAME..."
if gcloud tasks queues describe $QUEUE_NAME --location=$LOCATION --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "✅ Fila '$QUEUE_NAME' já existe."
else
    echo "⚠️ Fila '$QUEUE_NAME' não encontrada. Criando..."
    gcloud tasks queues create $QUEUE_NAME \
        --location=$LOCATION \
        --project=$PROJECT_ID \
        --max-dispatches-per-second=10 \
        --max-concurrent-dispatches=50
    echo "✅ Fila criada com sucesso."
fi

# 2. Drive Webhook Registration
echo "🔗 Registrando Webhook do Drive..."
echo "Target URL: $APP_URL/api/webhook/renew"

# Call the renew endpoint
RESPONSE=$(curl -s -X POST "$APP_URL/api/webhook/renew")
echo "Resposta do Servidor: $RESPONSE"

if [[ "$RESPONSE" == *"success"* ]]; then
    echo "✅ Webhook Registrado/Renovado com Sucesso!"
else
    echo "❌ Falha ao registrar Webhook. Verifique se a aplicação já subiu."
fi

echo "🎉 Configuração Concluída!"
