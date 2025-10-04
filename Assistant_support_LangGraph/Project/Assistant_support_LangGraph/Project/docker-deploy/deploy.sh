# ============================================
# deploy.sh - Script per deployare il container
# ============================================

echo "🚀 Deploying LangGraph API..."

# Controlla se il file .env criptato esiste
ENV_FILE="/var/www/webapi/langgraph-api/config/LNX-CLKS004-CLKAPP792.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  ATTENZIONE: File .env criptato non trovato in $ENV_FILE"
    echo "   Assicurati di copiarlo prima di continuare!"
    read -p "Vuoi continuare comunque? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Imposta la chiave di cifratura (IMPORTANTE: sostituisci con la tua chiave reale)
#export CHIAVE_CIFRATURA=""

# Ferma e rimuovi container esistente se presente
echo "🔄 Fermando container esistente..."
docker compose down

# Avvia il nuovo container
echo "🔥 Avviando nuovo container..."
docker compose up -d

# Attendi che il container sia healthy
echo "⏳ Attendendo che l'API sia pronta..."
sleep 5

# Controlla lo stato
if docker ps | grep -q langgraph-api; then
    echo "✅ Container avviato con successo!"
    
    # Mostra i logs
    echo "📜 Ultimi log del container:"
    docker logs --tail 20 langgraph-api
    
    # Test dell'endpoint
    echo "🧪 Test endpoint salute:"
    curl -s http://localhost:8000/ | jq . || echo "API raggiungibile su http://localhost:8000"
else
    echo "❌ Container non avviato!"
    echo "📜 Logs di errore:"
    docker logs langgraph-api
    exit 1
fi

echo "✨ Deploy completato!"
echo "📍 API disponibile su: http://localhost:8000"
echo "📊 Per vedere i logs: docker logs -f langgraph-api"
echo "🛑 Per fermare: docker compose down"

# ============================================
# restart.sh - Script per restart rapido
# ============================================

#!/bin/bash
echo "🔄 Restarting LangGraph API..."
docker-compose restart langgraph-api
echo "✅ Restart completato!"
docker logs --tail 10 langgraph-api

# ============================================
# logs.sh - Script per vedere i logs
# ============================================

#!/bin/bash
docker logs -f --tail 100 langgraph-api

# ============================================
# shell.sh - Script per entrare nel container
# ============================================

#!/bin/bash
docker exec -it langgraph-api /bin/bash