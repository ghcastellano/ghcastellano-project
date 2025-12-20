#!/bin/bash
set -e

IMAGE_NAME="mvp-web-local"

# Verifica se .env existe
if [ ! -f ".env" ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "   Para rodar localmente, você precisa restaurar seu .env com as chaves."
    echo "   (Use o .env.bak como referência se tiver, ou crie um novo)"
    exit 1
fi

echo "🐳 Construindo imagem Docker local ($IMAGE_NAME)..."
docker build -t $IMAGE_NAME .

echo "▶️  Iniciando Container em localhost:8080..."
echo "    (Para parar, pressione Ctrl+C)"
echo ""

docker run --rm -it \
  -p 8080:8080 \
  --env-file .env \
  -e PORT=8080 \
  -e FLASK_DEBUG=1 \
  $IMAGE_NAME
