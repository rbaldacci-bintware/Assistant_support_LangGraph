# graph_nodes.py
import os
import requests
from .state import GraphState

# URL dell'API Google che hai sviluppato - legge da variabile d'ambiente
API_URL = os.getenv("GOOGLE_API_URL", "http://localhost:5020")

def conversation_reconstruction_node(state: GraphState) -> dict:
    """
    Nodo che prende due file audio e ricostruisce la conversazione.
    """
    print("--- ESECUZIONE NODO RICOSTRUZIONE CONVERSAZIONE ---")
    
    if len(state["audio_file_paths"]) != 2:  # ← CORRETTO
        raise ValueError("Sono richiesti esattamente due file audio.")
    
    tenant_key = state.get("tenant_key")
    if not tenant_key:
        raise ValueError("tenant_key non trovato nello stato del grafo.")
        
    print(f"Invio richiesta all'API Google con tenant_key come parametro URL: {tenant_key}")
    
    # Prepara i parametri per la query string
    params = {
        "tenant_key": tenant_key
    }

    files = []
    for file_path in state["audio_file_paths"]:
        with open(file_path, "rb") as f:
            ext = os.path.splitext(file_path)[1][1:]
            mime_type = f"audio/{ext}"
            file_content = f.read()
            files.append(('files', (os.path.basename(file_path), file_content, mime_type)))
    
    response = requests.post(f"{API_URL}/api/Audio/reconstruct", files=files, params=params)
    
    
    if response.status_code == 200:
        # response.json() converte la stringa di testo in un dizionario
        data = response.json()
        
        # Ora usa la chiave corretta (camelCase) per estrarre il valore
        transcript = data["reconstructedTranscript"]
        
        print("--- RICOSTRUZIONE RICEVUTA CON SUCCESSO ---")
        print(transcript)
        
        return {"transcript": transcript}
    else:
        raise Exception(f"Errore API: {response.status_code}")