# Usa Python 3.11 slim per dimensioni ridotte
FROM python:3.11-slim

# Imposta directory di lavoro
WORKDIR /app

# Installa dipendenze di sistema necessarie per alcune librerie Python
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copia prima requirements per sfruttare Docker cache
COPY requirements.txt .

# Installa dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione
COPY app/ ./app/

# Copia config.json (quello con i path che poi modificheremo)
COPY config.json .

# Crea directory per file temporanei
RUN mkdir -p /tmp/audio

# Esponi la porta 8000
EXPOSE 8000

# Variabili d'ambiente che possono essere sovrascritte
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_API_URL=http://localhost:5020
ENV FileApiBaseUrl=http://localhost:5019

# Comando di avvio
CMD ["uvicorn", "app.main:api", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]