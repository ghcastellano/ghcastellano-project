#!/bin/bash
# scripts/cleanup_images.sh
# Mantém apenas as últimas N imagens no Artifact Registry para economizar Storage.

KEEP_COUNT=5
PROJECT_ID=${GCP_PROJECT_ID:-"projeto-poc-ap"}
REPO_NAME="mvp-web"
# IMAGE_NAME="mvp-web" # Não usado em GCR root
FULL_IMAGE_PATH="gcr.io/$PROJECT_ID/$REPO_NAME"

echo "🧹 Iniciando limpeza de imagens em: $FULL_IMAGE_PATH"
echo "   Mantendo as últimas $KEEP_COUNT imagens..."

# Lista todos os digests ordenados por data (mais antigos primeiro), excluindo os últimos N
# Nota: O comando gcloud list retorna json, usamos jq ou sort/formatting bash simples.
# Por simplicidade e robustez, vamos deletar por TAG ou DIGEST.

# 1. Listar digests com data (formato legado GCR)
echo "🔍 Buscando imagens em gcr.io..."

# gcloud container images list-tags retorna lista. Ordenamos por timestamp.
# --sort-by=~timestamp coloca mais recentes primeiro.
# tail -n +X pega do X em diante (antigos).
DIGESTS_TO_DELETE=$(gcloud container images list-tags $FULL_IMAGE_PATH \
  --sort-by=~timestamp \
  --format="value(digest)" | tail -n +$((KEEP_COUNT + 1)))

if [ -z "$DIGESTS_TO_DELETE" ]; then
    echo "✅ Nenhuma imagem antiga para deletar. (Total <= $KEEP_COUNT)"
    exit 0
fi

COUNT=$(echo "$DIGESTS_TO_DELETE" | wc -l)
echo "🗑️ Encontradas $COUNT imagens antigas para deletar."

# Loop para deletar
for DIGEST in $DIGESTS_TO_DELETE; do
    # Garante que o digest tenha o prefixo sha256:
    if [[ "$DIGEST" != sha256:* ]]; then
        DIGEST="sha256:$DIGEST"
    fi
    echo "   - Deletando $DIGEST..."
    gcloud container images delete "$FULL_IMAGE_PATH@$DIGEST" --force-delete-tags --quiet
done

echo "🎉 Limpeza concluída! Apenas as últimas $KEEP_COUNT imagens foram mantidas."
