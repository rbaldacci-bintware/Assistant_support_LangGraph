#!/usr/bin/env python3
"""
File per lanciare l'API in modalità debug direttamente da VS Code
Usa: Clic destro → Python Debugger: Debug Python File
"""
import os
import sys

# Imposta la directory di lavoro sulla cartella Project
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)  # Cambia la directory di lavoro alla cartella Project

print(f"📁 Directory di lavoro impostata su: {os.getcwd()}")

# Aggiungi il path corrente al PYTHONPATH
sys.path.insert(0, script_dir)

import uvicorn

if __name__ == "__main__":
    print("🚀 Avvio server FastAPI in modalità debug...")
    print(f"✅ config.json esiste: {os.path.exists('config.json')}")
    
    # Avvia l'applicazione
    # reload=False per il debug (altrimenti crea un processo separato)
    uvicorn.run(
        "app.main:api",
        host="0.0.0.0",
        port=8000,
        reload=False,  # IMPORTANTE: False per il debug!
        log_level="info"
    )