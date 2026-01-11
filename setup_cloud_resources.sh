#!/bin/bash
set -e

# Configurações
PROJECT_ID="projeto-poc-ap"
REGION="us-central1"
SERVICE_NAME="mvp-web"
BUCKET_NAME="assets-${PROJECT_ID}" # Nomes de bucket devem ser globais, usando ID do projeto ajuda
SCHEDULER_JOB_NAME="sync-drive-cron"
SERVICE_ACCOUNT_EMAIL=""

echo "🚀 Iniciando Setup de Infraestrutura Cloud..."

# 1. Obter URL do Serviço e Conta de Serviço
echo "🔍 Obtendo dados do Cloud Run..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
SERVICE_ACCOUNT_EMAIL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(spec.template.spec.serviceAccountName)')

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Erro: Não foi possível obter a URL do serviço. O deploy foi feito?"
    exit 1
fi

if [ -z "$SERVICE_ACCOUNT_EMAIL" ]; then
    # Fallback para default compute service account se não especificado
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')
    SERVICE_ACCOUNT_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    echo "⚠️  Service Account não explícita no Run. Usando padrão estimada: $SERVICE_ACCOUNT_EMAIL"
fi

echo "✅ Serviço detectado: $SERVICE_URL"
echo "✅ Conta de Serviço: $SERVICE_ACCOUNT_EMAIL"

# 2. Criar Bucket (Se não existir)
echo "--------------------------------------------------"
echo "📦 Configurando Google Cloud Storage..."
if gcloud storage buckets describe gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "✅ Bucket gs://$BUCKET_NAME já existe."
else
    echo "🆕 Criando bucket gs://$BUCKET_NAME..."
    gcloud storage buckets create gs://$BUCKET_NAME --location=$REGION --uniform-bucket-level-access
    # Tornar público para leitura (Opcional, removemos "allUsers" se quiser privado)
    # gcloud storage buckets add-iam-policy-binding gs://$BUCKET_NAME --member=allUsers --role=roles/storage.objectViewer
fi

# 3. Dar permissão para o Cloud Run ler/escrever no Bucket
echo "🔑 Ajustando permissões do Bucket..."
gcloud storage buckets add-iam-policy-binding gs://$BUCKET_NAME \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.objectAdmin" > /dev/null
echo "✅ Permissão 'Storage Object Admin' concedida a $SERVICE_ACCOUNT_EMAIL"

# 4. Atualizar Cloud Run com o nome do Bucket
echo "🔄 Atualizando Cloud Run com env var GCP_STORAGE_BUCKET..."
gcloud run services update $SERVICE_NAME \
    --region $REGION \
    --update-env-vars GCP_STORAGE_BUCKET=$BUCKET_NAME

# 5. Criar Cloud Scheduler
echo "--------------------------------------------------"
echo "⏰ Configurando Cloud Scheduler..."

# Habilitar API se necessário
gcloud services enable cloudscheduler.googleapis.com

TARGET_URI="${SERVICE_URL}/api/cron/sync_drive"

# if gcloud scheduler jobs describe $SCHEDULER_JOB_NAME --location=$REGION > /dev/null 2>&1; then
#     echo "🔄 Atualizando Job existente: $SCHEDULER_JOB_NAME"
#     gcloud scheduler jobs update http $SCHEDULER_JOB_NAME \
#         --location=$REGION \
#         --schedule="*/15 * * * *" \
#         --uri="$TARGET_URI" \
#         --http-method=POST \
#         --oidc-service-account-email=$SERVICE_ACCOUNT_EMAIL \
#         --oidc-token-audience=$TARGET_URI
# else
#     echo "🆕 Criando Job: $SCHEDULER_JOB_NAME"
#     gcloud scheduler jobs create http $SCHEDULER_JOB_NAME \
#         --location=$REGION \
#         --schedule="*/15 * * * *" \
#         --uri="$TARGET_URI" \
#         --http-method=POST \
#         --oidc-service-account-email=$SERVICE_ACCOUNT_EMAIL \
#         --oidc-token-audience=$TARGET_URI
# fi
# echo "✅ Cloud Scheduler configurado para bater em $TARGET_URI a cada 15 min."

echo "--------------------------------------------------"
echo "🎉 Setup CLOUD concluído com sucesso!"
echo "📂 Bucket: gs://$BUCKET_NAME"
echo "⏰ Scheduler: $SCHEDULER_JOB_NAME"
