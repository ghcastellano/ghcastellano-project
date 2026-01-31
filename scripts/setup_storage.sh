#!/bin/bash
# Script para configurar Google Cloud Storage para evidências
# Autor: Claude Sonnet 4.5
# Data: 2026-01-31

set -e

PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="${PROJECT_ID}-mvp-evidences"
REGION="us-central1"
SERVICE_NAME="mvp-web"

echo "🚀 Configurando Google Cloud Storage..."
echo "📦 Projeto: $PROJECT_ID"
echo "🪣 Bucket: $BUCKET_NAME"
echo ""

# 1. Criar bucket se não existir
echo "📝 Verificando se bucket existe..."
if ! gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo "✨ Criando bucket..."
    gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://${BUCKET_NAME}
    echo "✅ Bucket criado: gs://${BUCKET_NAME}"
else
    echo "✅ Bucket já existe: gs://${BUCKET_NAME}"
fi

# 2. Configurar CORS para permitir upload do navegador
echo ""
echo "🔧 Configurando CORS..."
cat > /tmp/cors.json <<EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "PUT", "POST", "DELETE"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

gsutil cors set /tmp/cors.json gs://${BUCKET_NAME}
echo "✅ CORS configurado"

# 3. Tornar bucket público para leitura (para as evidências serem acessíveis)
echo ""
echo "🌐 Tornando arquivos públicos para leitura..."
gsutil iam ch allUsers:objectViewer gs://${BUCKET_NAME}
echo "✅ Permissões configuradas (leitura pública)"

# 4. Atualizar variável de ambiente no Cloud Run
echo ""
echo "☁️ Atualizando variável de ambiente no Cloud Run..."
gcloud run services update ${SERVICE_NAME} \
  --region ${REGION} \
  --update-env-vars GCP_STORAGE_BUCKET=${BUCKET_NAME} \
  --quiet

echo "✅ Variável GCP_STORAGE_BUCKET configurada no Cloud Run"

echo ""
echo "🎉 Configuração concluída com sucesso!"
echo ""
echo "📋 Resumo:"
echo "  - Bucket: gs://${BUCKET_NAME}"
echo "  - URL pública: https://storage.googleapis.com/${BUCKET_NAME}/"
echo "  - Variável de ambiente: GCP_STORAGE_BUCKET=${BUCKET_NAME}"
echo ""
echo "ℹ️  Aguarde o deploy do Cloud Run finalizar para as mudanças terem efeito."
echo "ℹ️  Após o deploy, as novas evidências serão salvas permanentemente no GCS."
