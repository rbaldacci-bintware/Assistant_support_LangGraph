# app/graph_nodes.py
import os
import json
import logging
import requests
from .state import GraphState
from .services import PersistenceClient, AudioTools
from .internal_api_client import InternalApiClient

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL delle API (lette da variabili d'ambiente, con fallback)
API_URL = os.getenv("GOOGLE_API_URL", "http://localhost:5020")
FILE_API_URL = os.getenv("FileApiBaseUrl", "http://localhost:5019")

# --- NODI DEL GRAFO ---

def conversation_reconstruction_node(state: GraphState) -> dict:
    """Nodo 1: Ricostruisce la conversazione da file audio."""
    print("--- NODO 1: RICOSTRUZIONE CONVERSAZIONE ---")
    
    # Flusso principale: usa i riferimenti ai file audio nello storage
    if state.get("location") and state.get("inbound") and state.get("outbound"):
        config = state.get("config", {})
        api_client = InternalApiClient(config)
        audio_tools = AudioTools(api_client)
        
        response = audio_tools.reconstruct_from_storage(
            location=state["location"],
            inbound_filename=state["inbound"],
            outbound_filename=state["outbound"],
            project_name=state["project_name"]
        )
        
        return {
            "transcript": response.reconstructedTranscript,
            "reconstruction": response.dict(),
            "tokens_used": response.usage.tokens,
            "cost_usd": response.usage.costUsd
        }
    
    # Flusso alternativo per test: usa percorsi di file locali
    elif len(state.get("audio_file_paths", [])) == 2:
        project_name = state.get("project_name")
        if not project_name:
            raise ValueError("project_name non trovato")
        
        params = {"project_name": project_name}
        files = []
        for file_path in state["audio_file_paths"]:
            with open(file_path, "rb") as f:
                ext = os.path.splitext(file_path)[1][1:]
                mime_type = f"audio/{ext}"
                file_content = f.read()
                files.append(('files', (os.path.basename(file_path), file_content, mime_type)))
        
        response = requests.post(f"{API_URL}/api/Audio/reconstruct", files=files, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "transcript": data["reconstructedTranscript"],
                "reconstruction": data,
                "tokens_used": data.get("usage", {}).get("tokens", 0),
                "cost_usd": data.get("usage", {}).get("costUsd", 0.0)
            }
    
    raise ValueError("Input non valido per la ricostruzione. Fornire 'location'/'inbound'/'outbound' o 'audio_file_paths'.")

def persistence_node(state: GraphState) -> dict:
    """Nodo 2: Salva la trascrizione nel database."""
    print("--- NODO 2: PERSISTENZA ---")
    
    if not state.get("conversation_id"):
        logger.warning("conversation_id non presente, skip persistenza.")
        return {"persistence_result": "SKIPPED"}
    
    config = state.get("config", {})
    api_client = InternalApiClient(config)
    persistence_client = PersistenceClient(api_client)
    
    result = persistence_client.save_conversation(
        conversation_id=state["conversation_id"],
        transcript=state["transcript"],
        type="TRASCRIZIONE"
    )
    
    logger.info(f"Persistenza: Status={result.status}, Id={result.id}")
    return {"persistence_result": f"{result.status}:{result.id}"}

def email_node(state: GraphState) -> dict:
    """Nodo 3: Invia email tramite API esterna."""
    print("--- NODO 3: EMAIL ---")
    
    # Controlla se l'invio email è richiesto
    scope = state.get("scope", [])
    if not scope:
        logger.info("Email non richiesta (scope non contiene MAIL_RT)")
        return {"email_result": "SKIPPED_NO_SCOPE"}
    
    # Ottieni la configurazione
    config = state.get("config", {})
    api_client = InternalApiClient(config)
    api_key = api_client.api_key
    
    # URL dell'API Email
    EMAIL_API_URL = os.getenv("EMAIL_API_URL", "http://localhost:5007")
    
    # Costruisci il payload nel formato richiesto
    graph_payload = {
        "graph": {
            "edges": [],
            "nodes": [
                {
                    "id": "email",
                    "type": "tool",
                    "plugin": "email",
                    "function": "send_reconstruction_email",
                    "outputKey": "emailResult",
                    "parameters": {
                        "scope": "{{scope}}",
                        "co_code": "{{co_code}}",
                        "user_id": "{{user_id}}",
                        "caller_id": "{{caller_id}}",
                        "orgn_code": "{{orgn_code}}",
                        "conversationId": "{{conversationId}}",
                        "tenant_key": "{{tenant_key}}",
                        "id_assistito": "{{id_assistito}}",
                        "transcript": "{{transcript}}"
                    }
                }
            ],
            "startNodeId": "email"
        },
        "input": "",
        "state": {
            "scope": state.get("scope", []),  # Default a MAIL_RT se non presente
            "co_code": state.get("co_code", "none"),
            "user_id": state.get("user_id", "none"),
            "caller_id": state.get("caller_id", "none"),
            "orgn_code": state.get("orgn_code", "none"),
            "conversationId": state.get("conversation_id", "none"),  # Nota: conversion_id -> conversationId
            "tenant_key": state.get("tenant_key", "none"),
            "id_assistito": state.get("id_assistito", "none"),  # Se non presente sarà None
            "transcript": state.get("transcript", "none")
        }
    }
    
    # Headers per la richiesta
    headers = {
        'accept': 'text/plain',
        'X-Api-Key': api_key,  # Usa la stessa InternalStaticKey
        'Content-Type': 'application/json'
    }
    
    try:
        logger.info(f"Invio email tramite API: {EMAIL_API_URL}/api/Graph/run")
        
        # Log del payload per debug (rimuovi i dati sensibili in produzione)
        logger.debug(f"Email payload: conversationId={graph_payload['state'].get('conversationId')}, "
                    f"user={graph_payload['state'].get('user_id')}")
        
        # Effettua la chiamata POST
        response = requests.post(
            f"{EMAIL_API_URL}/api/Graph/run",
            json=graph_payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info("✅ Email inviata con successo")
            return {
                "email_result": "SUCCESS",
                "email_response": response.text
            }
        else:
            logger.error(f"❌ Errore invio email: Status={response.status_code}, Body={response.text}")
            return {
                "email_result": f"ERROR_{response.status_code}",
                "email_error": response.text
            }
            
    except requests.exceptions.Timeout:
        logger.error("⏱️ Timeout durante l'invio dell'email")
        return {"email_result": "TIMEOUT"}
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Errore di rete durante l'invio email: {str(e)}")
        return {"email_result": "NETWORK_ERROR", "email_error": str(e)}
    except Exception as e:
        logger.error(f"❌ Errore generico durante l'invio email: {str(e)}")
        return {"email_result": "ERROR", "email_error": str(e)}

def _download_file(location: str, file_name: str, api_key: str) -> bytes:
    """Funzione helper per scaricare un file come array di byte."""
    url = f"{FILE_API_URL}/api/files/{location}/{file_name}"
    headers = {'Accept': 'application/octet-stream', 'X-Api-Key': api_key}
    try:
        logger.info(f"Download knowledge base file da: {url}")
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Errore durante il download del file {file_name}: {e}")
        return None

def analysis_node(state: GraphState) -> dict:
    """Nodo 4: Scarica i file di KB e invia tutto all'API C# per l'analisi."""
    print("--- NODO 4: ANALISI AI ---")

    transcript_content = state.get("transcript")
    if not transcript_content:
        raise ValueError("La trascrizione non è presente nello stato e non può essere analizzata.")
    
    config = state.get("config", {})
    api_client = InternalApiClient(config)
    internal_api_key = api_client.api_key

    analysis_prompt = """Analizza la trascrizione della conversazione educativa/terapeutica e genera un'analisi strutturata seguendo questi punti:
          FASE 1: ANALISI PER CLUSTER DI OSSERVAZIONE
         Per ogni cluster, valuta su scala 1-4 (critico, emergente, funzionale con supporto, autonomo):
          1. COMUNICAZIONE FUNZIONALE
            - Efficacia nell'esprimere bisogni e desideri
            - Uso del linguaggio verbale, gesti o supporti alternativi
          2. AUTONOMIA PERSONALE
            - Capacità di gestire attività quotidiane (igiene, alimentazione, vestirsi)
          3. GIOCO E PARTECIPAZIONE
            - Modalità di interazione nelle attività ludiche
            - Livello di iniziativa mostrato
          4. SOCIALIZZAZIONE
            - Ricerca del contatto con adulti o pari
            - Risposta agli inviti all'interazione
          5. GESTIONE DELLA DISREGOLAZIONE
            - Identificazione dei trigger che scatenano crisi
            - Tipo di risposta comportamentale (blocco, rabbia, pianto)
          6. TOLLERANZA ALLA FRUSTRAZIONE
            - Reazioni di fronte a 'no', errori o attese
          7. PIANIFICAZIONE SPAZIO-TEMPORALE
            - Orientamento nello spazio e nel tempo delle attività
          8. REGOLAZIONE RISPETTO AL CONTESTO
            - Rispetto delle regole
            - Accettazione delle indicazioni dell'adulto
          FASE 2: ANALISI DELL'INTERAZIONE OPERATORE-UTENTE
         - Qualità della comunicazione dell'operatore
         - Efficacia delle strategie utilizzate
         - Stato emotivo dell'operatore
          FASE 3: IDENTIFICAZIONE PATTERN E INSIGHT
         - Correlazioni significative
         - Segnali premonitori non colti
         - Interessi emergenti utilizzabili come rinforzi
          FASE 4: GENERAZIONE SUGGERIMENTI
         - Report di sintesi con punti di forza e aree di miglioramento
         - Strategie alternative basate sulle evidenze
         - Strumenti e attività consigliati dal documento di riferimento
         - Obiettivi SMART per la prossima sessione
         - Checklist di dati da raccogliere
          Restituisci l'analisi in formato JSON strutturato."""

    # ✅ VALIDAZIONE: Verifica che i file di knowledge base siano specificati
    knowledge_base_files_to_download = state.get("knowledge_base_files", [])
    
    if not knowledge_base_files_to_download:
        error_msg = "❌ Nessun file di knowledge base specificato nello stato. L'analisi richiede almeno un file."
        logger.error(error_msg)
        return {
            "error": "MISSING_KNOWLEDGE_BASE_FILES",
            "details": error_msg,
            "final_status": "ERROR"
        }
    
    logger.info(f"Download di {len(knowledge_base_files_to_download)} file di knowledge base")

    # Download dei file
    downloaded_files_content = []
    for file_info in knowledge_base_files_to_download:
        location = file_info.get("location")
        file_name = file_info.get("fileName")
        
        if not location or not file_name:
            error_msg = f"File info incompleto: {file_info}. Richiesti 'location' e 'fileName'"
            logger.error(error_msg)
            return {
                "error": "INVALID_FILE_INFO",
                "details": error_msg,
                "final_status": "ERROR"
            }
            
        logger.info(f"Download file: {file_name} da location: {location}")
        file_bytes = _download_file(location, file_name, internal_api_key)
        
        if not file_bytes:
            error_msg = f"Impossibile scaricare il file di knowledge base: {file_name} da {location}"
            logger.error(error_msg)
            return {
                "error": "DOWNLOAD_FAILED",
                "details": error_msg,
                "failed_file": file_name,
                "final_status": "ERROR"
            }
        
        downloaded_files_content.append((file_name, file_bytes))

    logger.info(f"✅ Scaricati con successo {len(downloaded_files_content)} file")

    # Preparazione form data
    form_data = {
        'prompt': analysis_prompt,
        'projectName': state["project_name"],
        'geminiModelName': 'gemini-2.5-pro'
    }

    # Upload dei file
    files_to_upload = []
    for file_name, file_bytes in downloaded_files_content:
        files_to_upload.append(('ListaKnowledgeBase', (file_name, file_bytes, 'application/pdf')))
    files_to_upload.append(('TrascrizioneFile', ('trascrizione.txt', transcript_content.encode('utf-8'), 'text/plain')))

    try:
        response = requests.post(
            f"{API_URL}/api/GeminiTextGeneration/analyze-file", 
            data=form_data,
            files=files_to_upload,
            timeout=180
        )

        if response.status_code == 200:
            gemini_response = response.json()
            analysis_text = gemini_response['candidates'][0]['content']['parts'][0]['text']
            analysis = json.loads(analysis_text)
            
            usage = gemini_response.get('usageMetadata', {})
            tokens_used = usage.get('totalTokenCount', 0)
            
            logger.info(f"✅ Analisi completata con successo. Tokens usati: {tokens_used}")
            return {
                "full_analysis": analysis,
                "analysis_tokens_used": tokens_used
            }
        else:
            logger.error(f"❌ Errore API analisi: Status {response.status_code}, Dettagli: {response.text}")
            return {
                "error": f"API_ERROR_{response.status_code}",
                "details": response.text,
                "final_status": "ERROR"
            }

    except Exception as e:
        logger.error(f"❌ Eccezione durante la chiamata di analisi: {str(e)}")
        return {
            "error": "EXCEPTION",
            "details": str(e),
            "final_status": "ERROR"
        }
    
def suggestions_node(state: GraphState) -> dict:
    """Nodo 5: Estrae l'analisi e i suggerimenti dallo stato."""
    print("--- NODO 5: ESTRAZIONE DATI DI ANALISI ---")
    
    full_analysis = state.get("full_analysis", {})
    
    # MODIFICA CHIAVE: Estrai ogni parte usando le chiavi snake_case corrette
    clusters = full_analysis.get("fase1_analisi_cluster", {})
    interaction = full_analysis.get("fase2_analisi_interazione", {})
    patterns = full_analysis.get("fase3_identificazione_pattern", {})
    suggestions = full_analysis.get("fase4_generazione_suggerimenti", {})
    
    if not full_analysis:
        logger.warning("Nessuna analisi completa trovata nello stato.")

    return {
        "cluster_analysis": clusters,
        "interaction_analysis": interaction,
        "patterns_insights": patterns,
        "suggestions": suggestions,
        "action_plan": suggestions.get("obiettivi_smart", [])
    }

def save_analysis_node(state: GraphState) -> dict:
    """Nodo 6: Salva l'analisi e i suggerimenti in due record separati."""
    print("--- NODO 6: SALVATAGGIO ANALISI E SUGGERIMENTI ---")

    conversation_id = state.get("conversation_id")
    if not conversation_id:
        logger.warning("conversation_id non presente, skip salvataggio.")
        return {"analysis_saved": False, "final_status": "SKIPPED"}

    # MODIFICA CHIAVE: Estrae i dati corretti dallo stato
    clusters = state.get("cluster_analysis", {})
    interaction = state.get("interaction_analysis", {})
    patterns = state.get("patterns_insights", {})
    suggestions = state.get("suggestions", {})
    
    if not clusters and not interaction and not patterns:
        logger.warning("Dati di analisi non sufficienti per il salvataggio.")
        return {"analysis_saved": False, "final_status": "SKIPPED"}

    config = state.get("config", {})
    api_client = InternalApiClient(config)
    persistence_client = PersistenceClient(api_client)

    # 1. Prepara e salva il blocco di ANALISI (Fasi 1-3)
    analysis_payload = {
        "fase1_analisi_cluster": clusters,
        "fase2_analisi_interazione": interaction,
        "fase3_identificazione_pattern": patterns
    }
    analysis_json_string = json.dumps(analysis_payload, indent=2, ensure_ascii=False)
    result_analysis = persistence_client.save_conversation(
        conversation_id=conversation_id,
        transcript=analysis_json_string,
        type="ANALISI"
    )
    logger.info(f"Salvataggio ANALISI: Status={result_analysis.status}, Id={result_analysis.id}")
    
    # 2. Prepara e salva il blocco dei SUGGERIMENTI (Fase 4)
    if suggestions:
        suggestions_json_string = json.dumps(suggestions, indent=2, ensure_ascii=False)
        result_suggestions = persistence_client.save_conversation(
            conversation_id=conversation_id,
            transcript=suggestions_json_string,
            type="SUGGERIMENTI"
        )
        logger.info(f"Salvataggio SUGGERIMENTI: Status={result_suggestions.status}, Id={result_suggestions.id}")

    return {
        "analysis_saved": True,
        "final_status": "COMPLETED"
    }