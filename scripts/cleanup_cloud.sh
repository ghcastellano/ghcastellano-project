#!/bin/bash
# Scripts para limpar revisões e imagens antigas (Zero Cost Architecture)
# Mantém apenas as 2 versões mais recentes.

SERVICE_NAME="mvp-web"
IMAGE_NAME="gcr.io/projeto-poc-ap/mvp-web"
REGION="us-central1"
PROJECT="projeto-poc-ap"

echo "🧹 Iniciando limpeza para $SERVICE_NAME no projeto $PROJECT..."

# 1. Limpar Revisões do Cloud Run (Mantendo 2 mais recentes)
echo "☁️  Verificando revisões antigas do Cloud Run..."
REVISIONS=$(gcloud run revisions list --service $SERVICE_NAME --region $REGION --project $PROJECT --sort-by=~createTime --format="value(name)" | tail -n +3)

if [ -z "$REVISIONS" ]; then
    echo "✅ Nenhuma revisão antiga para deletar."
else
    echo "🗑️  Deletando as seguintes revisões antigas:"
    echo "$REVISIONS"
    # Loop para deletar (xargs as vezes falha com input vazio ou multiline format)
    for REV in $REVISIONS; do
        gcloud run revisions delete "$REV" --region $REGION --project $PROJECT --quiet
    done
fi

# 2. Limpar Imagens do Container Registry (Mantendo 2 mais recentes)
echo "🐳 Verificando imagens antigas no GCR..."
DIGESTS=$(gcloud container images list-tags $IMAGE_NAME --project $PROJECT --sort-by=~TIMESTAMP --format="get(digest)" | tail -n +3)

if [ -z "$DIGESTS" ]; then
    echo "✅ Nenhuma imagem antiga para deletar."
else
    echo "🗑️  Deletando imagens antigas..."
    for DIGEST in $DIGESTS; do
        FULL_IMAGE="$IMAGE_NAME@$DIGEST"
        echo "Deletando $FULL_IMAGE"
        gcloud container images delete "$FULL_IMAGE" --project $PROJECT --quiet --force-delete-tags
    done
fi

echo "✨ Limpeza concluída! Apenas 2 versões mantidas."
