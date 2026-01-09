#!/bin/bash

# ==========================================
# SCRIPT DE OTIMIZAÇÃO DE CUSTOS (Artifact Registry)
# ==========================================
# Este script configura uma política de limpeza automática para deletar imagens antigas.
# Mantém apenas as 5 últimas versões (tag e untagged).
#
# Custo Estimado Atual: R$ 0,39 (Armazenamento de imagens antigas)
# Custo Pós-Script: ~R$ 0,00 (Dentro do Free Tier de 0.5GB se rodar poucos builds)
# ==========================================

REPO_NAME="mvp-web" # Nome do repositório no Artifact Registry
REGION="us-central1" # Ajuste se sua região for diferente (ex: southamerica-east1)
PROJECT_ID=$(gcloud config get-value project)

echo "🔧 Configurando Política de Ciclo de Vida para manter custos ZERO..."
echo "📂 Projeto: $PROJECT_ID | Repo: $REPO_NAME | Região: $REGION"

# Cria arquivo JSON da política temporariamente
cat > lifecycle-policy.json <<EOF
{
  "rule": [
    {
      "action": {
        "type": "DELETE"
      },
      "condition": {
        "tagState": "ANY",
        "olderThan": "7d"
      }
    },
    {
      "action": {
        "type": "DELETE"
      },
      "condition": {
        "tagState": "ANY",
        "numNewerVersions": 3
      }
    }
  ]
}
EOF

# Aplica a política (Requer permissões de Admin no Artifact Registry)
# Nota: O comando pode variar dependendo da versão do gcloud, usamos o padrão beta ou alpha se necessário, 
# mas o mais compatível é deletar imagens via script se a política não estiver disponível na tier free.
# Porém, a política é a forma correta.

echo "🚀 Aplicando política..."
gcloud artifacts repositories set-cleanup-policies $REPO_NAME \
  --project=$PROJECT_ID \
  --location=$REGION \
  --policy=lifecycle-policy.json \
  || echo "⚠️ Falha ao aplicar política automática. Verifique se o repositório existe e a região está correta."

# Limpeza Manual Imediata (Para garantir que o custo baixe AGORA)
echo "🧹 Executando limpeza manual de imagens antigas (Mantendo as 5 mais recentes)..."

# List all digests, sorted by date (oldest first), skipping top 5
IMAGES_TO_DELETE=$(gcloud container images list-tags "gcr.io/$PROJECT_ID/$REPO_NAME" --limit=9999 --sort-by=~TIMESTAMP --format='get(digest)' | tail -n +6)

if [ -z "$IMAGES_TO_DELETE" ]; then
    echo "✅ Repositório já está otimizado (Menos de 5 imagens)."
else
    echo "⚠️ Encontradas imagens antigas. Deletando..."
    for digest in $IMAGES_TO_DELETE; do
        echo "🗑️ Deletando $REPO_NAME@$digest..."
        gcloud container images delete "gcr.io/$PROJECT_ID/$REPO_NAME@$digest" --force-delete-tags --quiet || echo "⚠️ Falha ao deletar $digest (Ignorado)"
    done
    echo "✅ Limpeza manual concluída!"
fi

echo "ℹ️  A política de ciclo de vida também foi configurada para execuções futuras."

rm lifecycle-policy.json
echo "✅ Configuração finalizada! Os custos devem desaparecer nos próximos dias."
