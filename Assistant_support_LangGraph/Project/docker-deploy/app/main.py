# main.py
import logging
import os
import tempfile
import requests
from typing import Optional
from fastapi import FastAPI, HTTPException, logger
from pydantic import BaseModel

# NON usare dotenv - le variabili d'ambiente devono essere lette solo dal processo
# per compatibilità con C#: Environment.GetEnvironmentVariable("CHIAVE_CIFRATURA", EnvironmentVariableTarget.Process)

from .graph import conversation_graph
from .state import GraphState
from .configuration import initialize_configuration, InvalidOperationException

try:
    from .graph import complete_graph
    COMPLETE_GRAPH_AVAILABLE = complete_graph is not None
except ImportError:
    COMPLETE_GRAPH_AVAILABLE = False
    complete_graph = None
    print("⚠️ Grafo completo non disponibile")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inizializza configurazione
config = None
try:
    if os.path.exists("config.json"):
        config = initialize_configuration("config.json")
        print("✅ Configurazione caricata con successo")
    else:
        print("⚠️ config.json non trovato - crealo con questa struttura:")
        print('''
{
  "EnvFileSettings": {
    "FileName": "172_16_10_52vsCLK793.env",
    "Directory": "C:\\\\Sviluppo\\\\FileConfigGenerati"
  }
}
''')
except Exception as e:
    print(f"⚠️ Errore inizializzazione configurazione: {str(e)}")
    config = None

api = FastAPI(
    title="LangGraph Audio Processing API",
    description="API per ricostruire conversazioni da file audio scaricati automaticamente.",
    version="1.0.0",
)

class ConversationRequest(BaseModel):
    """Modello per la richiesta di trascrizione conversazione."""
    base_filename: str  # Es: "72aaba06-4267-443f-bf87-f50141e97734_"
    tenant_key: str

def download_audio_file(filename: str, api_key: str, api_base_url: str) -> str:
    """
    Scarica un file audio dall'API e lo salva in una directory temporanea.
    
    Args:
        filename: Nome completo del file (es. "72aaba06-4267-443f-bf87-f50141e97734_inbound.mp3")
        api_key: Chiave API per autenticazione
        api_base_url: URL base dell'API
    
    Returns:
        Il percorso del file scaricato
    """
    url = f"{api_base_url}/api/files/conversations-audio/{filename}"
    headers = {
        'accept': 'text/plain',
        'X-Api-Key': api_key
    }
    
    print(f"Scaricamento file da: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Crea un file temporaneo per salvare l'audio
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        print(f"File scaricato con successo: {temp_path}")
        return temp_path
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Errore nel download del file {filename}: {str(e)}"
        )

@api.get("/")
async def root():
    """Endpoint di benvenuto."""
    return {"message": "LangGraph Audio API - Invia il nome base del file per la ricostruzione"}

@api.post("/transcribe-conversation/")
async def transcribe_conversation(request: ConversationRequest):
    """
    Accetta il nome base di una conversazione, scarica i file audio inbound/outbound
    e ricostruisce la conversazione.
    
    Esempio di richiesta:
    {
        "base_filename": "72aaba06-4267-443f-bf87-f50141e97734_",
        "tenant_key": "CHIAVE_CLIENTE_123"
    }
    """
    if not config:
        raise HTTPException(
            status_code=500, 
            detail="Configurazione non inizializzata"
        )
    
    # Ottieni API key dalla configurazione
    try:
        api_key = config["InternalStaticKey"]
       
        # TEMPORANEO: Usa la chiave corretta per testare il sistema
        if len(api_key) > 50:
            print("[WARNING] La chiave API sembra essere ancora criptata!")
            print("[INFO] Uso temporaneamente la chiave corretta per test...")
            
            print(f"[INFO] Usando API Key di test: {api_key}")
    except InvalidOperationException as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
    # Ottieni URL dell'API dalla configurazione o usa default
    api_base_url = config.get("FileApiBaseUrl", "http://localhost:5019")
    
    # Costruisci i nomi completi dei file
    base_name = request.base_filename.rstrip('_')  # Rimuovi underscore finale se presente
    inbound_filename = f"{base_name}_inbound.mp3"
    outbound_filename = f"{base_name}_outbound.mp3"
    
    temp_files = []
    
    try:
        # Scarica i due file audio
        print(f"Download dei file audio per: {base_name}")
        
        inbound_path = download_audio_file(inbound_filename, api_key, api_base_url)
        temp_files.append(inbound_path)
        
        outbound_path = download_audio_file(outbound_filename, api_key, api_base_url)
        temp_files.append(outbound_path)
        
        # Prepara lo stato con i percorsi dei file scaricati
        initial_state: GraphState = {
            "messages": [],
            "audio_file_paths": [inbound_path, outbound_path],
            "transcript": "",
            "tenant_key": request.tenant_key,
        }
        
        print(f"Elaborazione file scaricati con tenant_key: {request.tenant_key}")
        print(f"  - Inbound: {inbound_path}")
        print(f"  - Outbound: {outbound_path}")
        
        # Esegui il grafo
        final_state = await conversation_graph.ainvoke(initial_state)
        transcript = final_state.get("transcript", "Ricostruzione non disponibile.")
        
        return {
            "base_filename": base_name,
            "files_processed": [inbound_filename, outbound_filename],
            "reconstructed_conversation": transcript
        }
    
    except HTTPException:
        raise  # Rilancia le HTTPException già gestite
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'elaborazione: {str(e)}")
    
    finally:
        # Pulisci i file temporanei
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"File temporaneo rimosso: {temp_file}")
            except Exception as e:
                print(f"Errore nella rimozione del file temporaneo {temp_file}: {e}")

@api.post("/transcribe-conversation-from-paths/")
async def transcribe_conversation_from_paths(paths: dict):
    """
    Endpoint alternativo che accetta percorsi locali (per test o uso diretto).
    
    Esempio:
    {
        "file1": "path/to/inbound.mp3",
        "file2": "path/to/outbound.mp3"
    }
    """
    file1 = paths.get("file1")
    file2 = paths.get("file2")
    
    if not file1 or not file2:
        raise HTTPException(status_code=400, detail="Sono richiesti file1 e file2")
    
    if not os.path.exists(file1):
        raise HTTPException(status_code=404, detail=f"File non trovato: {file1}")
    if not os.path.exists(file2):
        raise HTTPException(status_code=404, detail=f"File non trovato: {file2}")
    
    try:
        initial_state: GraphState = {
            "messages": [],
            "audio_file_paths": [file1, file2],
            "transcript": "",
        }
        
        final_state = await conversation_graph.ainvoke(initial_state)
        transcript = final_state.get("transcript", "Ricostruzione non disponibile.")
        
        return {
            "files_processed": [file1, file2],
            "reconstructed_conversation": transcript
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore: {str(e)}")
    


    
@api.post("/api/graph/run")
async def run_dynamic_workflow(request: dict):
    """
    Endpoint universale per eseguire workflow dinamici.
    
    Supporta:
    - workflow: nome preset ("full", "quick", "analysis_only") o lista custom ["reconstruct", "email"]
    - state: stato iniziale con tutti i dati necessari
    """
    if not config:
        raise HTTPException(status_code=500, detail="Configurazione non inizializzata")
    
    try:
        # Estrai parametri dalla richiesta
        input_state = request.get("state", {})
        workflow_spec = request.get("workflow", "full")  # Default: flusso completo
        
        # Prepara i passi del workflow
        from app.graph import prepare_workflow_steps
        steps = prepare_workflow_steps(workflow_spec)
        
        if not steps:
            raise HTTPException(
                status_code=400, 
                detail="Nessun passo valido nel workflow richiesto"
            )
        
        logger.info(f"🚀 Avvio workflow con passi: {steps}")
        
        # Prepara stato iniziale
        initial_state: GraphState = {
            # Campi base
            "messages": [],
            "audio_file_paths": [],
            "transcript": input_state.get("transcript", ""),
            
            # Identificazione
            "tenant_key": input_state.get("tenant_key"),
            "conversation_id": input_state.get("conversationId"),
            "co_code": input_state.get("co_code"),
            "orgn_code": input_state.get("orgn_code"),
            "user_id": input_state.get("user_id"),
            "caller_id": input_state.get("caller_id"),
            "scope": input_state.get("scope", []),
            "id_assistito": input_state.get("id_assistito"),
            # File storage
            "location": input_state.get("location"),
            "inbound": input_state.get("inbound"),
            "outbound": input_state.get("outbound"),
            "project_name": input_state.get("project_name"),
            "knowledge_base_files": input_state.get("knowledge_base_files"),  
            # Pre-popolamento per entrare a metà flusso
            "reconstruction": input_state.get("reconstruction"),
            "cluster_analysis": input_state.get("cluster_analysis"),
            
            # Configurazione
            "config": {
                "InternalStaticKey": config["InternalStaticKey"],
                "RemoteApi": {
                    "BaseUrl": config.get("RemoteApi.BaseUrl", "http://localhost:5010"),
                    "BaseUrlGoogleApi": config.get("RemoteApi.BaseUrlGoogleApi", "http://localhost:5020"),
                    "BaseUrlFileService": config.get("FileApiBaseUrl", "http://localhost:5019")
                }
            },
            
            # 🆕 Controllo del flusso
            "steps": steps,
            "current_step_index": 0,
            "execution_trace": [],
            "skip_remaining": False,
            "error": None,
            
            # Risultati inizializzati
            "persistence_result": None,
            "email_result": None,
            "suggestions": None,
            "action_plan": None,
            "tokens_used": 0,
            "cost_usd": 0.0,
            "analysis_saved": False,
            "final_status": None
        }
        
        # Esegui il workflow
        from app.graph import dynamic_graph
        final_state = await dynamic_graph.ainvoke(initial_state)
        
        # Costruisci risposta
        return {
            "success": not bool(final_state.get("error")),
            "workflow_executed": steps,
            "execution_trace": final_state.get("execution_trace", []),
            "state": {
                "conversation_id": final_state.get("conversation_id"),
                "transcript": final_state.get("transcript", ""),
                "persistence_result": final_state.get("persistence_result"),
                "email_result": final_state.get("email_result"),
                "tokens_used": final_state.get("tokens_used", 0),
                "cost_usd": final_state.get("cost_usd", 0.0),
                "analysis": {
                    "clusters": final_state.get("cluster_analysis", {}),
                    "interaction": final_state.get("interaction_analysis", {}),
                    "patterns": final_state.get("patterns_insights", {})
                },
                "suggestions": final_state.get("suggestions", {}),
                "action_plan": final_state.get("action_plan", {}),
                "final_status": final_state.get("final_status", "COMPLETED")
            },
            "error": final_state.get("error")
        }
        
    except Exception as e:
        logger.error(f"Errore nel workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# NUOVO endpoint per info sui workflow disponibili
@api.get("/api/graph/workflows")
async def get_available_workflows():
    """
    Restituisce informazioni sui workflow disponibili.
    """
    from app.graph import NODE_FUNCTIONS, PRESET_WORKFLOWS, DEFAULT_FLOW
    
    return {
        "available_nodes": list(NODE_FUNCTIONS.keys()),
        "preset_workflows": PRESET_WORKFLOWS,
        "default_flow": DEFAULT_FLOW,
        "usage_examples": {
            "full_flow": {
                "description": "Esegue il flusso completo",
                "workflow": "full"
            },
            "custom_flow": {
                "description": "Esegue solo alcuni nodi in ordine custom", 
                "workflow": ["reconstruct", "analyze", "persist"]
            },
            "single_node": {
                "description": "Esegue un singolo nodo",
                "workflow": ["email"]
            }
        }
    }
