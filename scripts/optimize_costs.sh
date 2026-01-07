#!/bin/bash
set -euo pipefail

# Config
PROJECT_ID="${GCP_PROJECT_ID:-projeto-poc-ap}"
REPO="gcr.io/$PROJECT_ID/mvp-web"

echo "💰 OTIMIZAÇÃO DE CUSTOS (MODO AGRESSIVO): Configurando limpeza..."
echo "📂 Repositório Alvo: $REPO"

# STRATEGY: Keep only the 2 most recent images (Current Active + 1 Backup)
# This prevents "Image Not Found" errors on Cold Starts if the deployment is very recent,
# while keeping costs to the absolute minimum (~$0.10/month).

echo "🧹 Limpando imagens antigas (Mantendo apenas as 2 últimas)..."

# List all digests, sorted by date (oldest first), skipping top 2
IMAGES_TO_DELETE=$(gcloud container images list-tags "$REPO" --limit=9999 --sort-by=~TIMESTAMP --format='get(digest)' | tail -n +3)

if [ -z "$IMAGES_TO_DELETE" ]; then
    echo "✅ Repositório já está otimizado (Menos de 2 imagens)."
else
    echo "⚠️ Encontradas imagens antigas. Deletando..."
    for digest in $IMAGES_TO_DELETE; do
        echo "🗑️ Deletando $REPO@$digest..."
        gcloud container images delete "$REPO@$digest" --force --quiet || echo "⚠️ Falha ao deletar $digest (Ignorado)"
    done
    echo "✅ Limpeza concluída! Custo estimado futuro: < R$ 1,00/mês."
fi
