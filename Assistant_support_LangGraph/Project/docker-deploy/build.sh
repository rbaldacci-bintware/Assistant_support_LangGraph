#!/bin/bash

# ============================================
# build.sh - Script per buildare l'immagine Docker
# ============================================

echo "🔨 Building Docker image for LangGraph API..."

# Nome e tag dell'immagine
IMAGE_NAME="langgraph-api"
IMAGE_TAG="latest"

# Build dell'immagine
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -eq 0 ]; then
    echo "✅ Build completato con successo!"
    echo "📦 Immagine creata: ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # Mostra dimensione immagine
    docker images ${IMAGE_NAME}:${IMAGE_TAG}
else
    echo "❌ Build fallito!"
    exit 1
fi