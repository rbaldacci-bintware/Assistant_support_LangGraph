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
        logger.info("Email non richiesta (scope vuoto)")
        return {"email_result": "SKIPPED_NO_SCOPE"}
    
    # Ottieni la configurazione
    config = state.get("config", {})
    api_client = InternalApiClient(config)
    api_key = api_client.api_key
    
    # URL dell'API Email
    EMAIL_API_URL = os.getenv("EMAIL_API_URL", "http://localhost:5007")
    
    # Prepara lo scope convertendolo sempre in lista
    scope_value = state.get("scope", [])
    if isinstance(scope_value, set):
        scope_value = list(scope_value)
    elif not isinstance(scope_value, list):
        scope_value = [scope_value] if scope_value else []
    

    full_analysis = state.get("full_analysis", {})
    analysis_json_string = json.dumps(full_analysis, ensure_ascii=False) if full_analysis else ""

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
                        "transcript": "{{transcript}}",
                        "structured_analysis": "{{structured_analysis}}"
                    }
                }
            ],
            "startNodeId": "email"
        },
        "input": "",
        "state": {
            "scope": scope_value,
            "co_code": state.get("co_code", "none"),
            "user_id": state.get("user_id", "none"),
            "caller_id": state.get("caller_id", "none"),
            "orgn_code": state.get("orgn_code", "none"),
            "conversationId": state.get("conversation_id", "none"),
            "tenant_key": state.get("tenant_key", "none"),
            "id_assistito": state.get("id_assistito", "none"),
            "transcript": state.get("transcript", "none"),
            "structured_analysis": analysis_json_string
        }
    }
    
    # Headers per la richiesta
    headers = {
        'accept': 'text/plain',
        'X-Api-Key': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        logger.info(f"Invio email tramite API: {EMAIL_API_URL}/api/Graph/run")
        logger.debug(f"Email payload scope: {scope_value}")
        
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
    analysis_prompt = """
**IL TUO RUOLO:**
Sei un assistente AI specializzato in pedagogia, con il compito di supportare un educatore.
La tua analisi deve essere **pratica, operativa e basata su un approccio educativo**.
**EVITA ASSOLUTAMENTE** qualsiasi linguaggio o riferimento che possa sembrare una diagnosi clinica, un'ipotesi psicologica o un parere psicoterapeutico. L'educatore conosce già la diagnosi dell'utente.
Il tuo obiettivo è fornire strumenti e spunti di riflessione concreti e immediatamente applicabili.

---

**FILE A TUA DISPOSIZIONE:**
- `trascrizione.txt`: La trascrizione della sessione educativa da analizzare.
- `Documento_di_Pianificazione_per_ORA.pdf`: Definisce i cluster di osservazione pedagogica con relativi descrittori. **Usa questo file come base per la FASE 1.**
- `Strumenti_e_attivita.pdf`: Un catalogo di strategie e strumenti pedagogici. **Usa questo file come riferimento principale per la FASE 4.**

---

**IL TUO COMPITO:**
Analizza la `trascrizione.txt` utilizzando i file PDF di riferimento e genera un'analisi strutturata in formato JSON, seguendo ESATTAMENTE le fasi e le direttive qui sotto.

---

**FASE 1: ANALISI PER CLUSTER DI OSSERVAZIONE**

Basandoti sulla trascrizione e sul file `Documento_di_Pianificazione_per_ORA.pdf`, valuta ogni cluster su una scala da 1 a 4.
- 1 = Critico (necessita intervento immediato)
- 2 = Emergente (competenza in sviluppo)
- 3 = Funzionale con supporto (autonomo con guida)
- 4 = Autonomo (competenza consolidata)

Per ogni cluster:
1. **Consulta il PDF** per identificare i descrittori specifici (punto b. del cluster)
2. **Cerca nella trascrizione** evidenze di questi descrittori
3. **Se trovi descrittori**, valuta il livello e citali
4. **Se NON trovi descrittori**, segui la regola sotto

**REGOLA PER MANCANZA DI EVIDENZE:**
Se un cluster NON ha evidenze nella trascrizione, usa ESATTAMENTE questa struttura:
{
  "livello": null,
  "evidenze": ["Nessuna evidenza diretta in questa sessione"],
  "descrittori_osservati": [],
  "note": "Non valutabile sulla base della trascrizione fornita. Raccomandare osservazione specifica su questo aspetto nelle prossime sessioni."
}

**CLUSTER DA VALUTARE:**
1. COMUNICAZIONE FUNZIONALE
2. AUTONOMIA PERSONALE
3. GIOCO E PARTECIPAZIONE
4. SOCIALIZZAZIONE
5. GESTIONE DELLA DISREGOLAZIONE
6. TOLLERANZA ALLA FRUSTRAZIONE
7. PIANIFICAZIONE SPAZIO-TEMPORALE
8. REGOLAZIONE RISPETTO AL CONTESTO

Per ogni cluster CON evidenze, fornisci:
- **livello**: Il punteggio numerico (1-4)
- **evidenze**: Citazioni specifiche dalla trascrizione
- **descrittori_osservati**: Lista dei descrittori dal PDF che hai identificato
- **note**: Brevi osservazioni qualitative con un taglio pedagogico

---

**FASE 2: ANALISI DELL'INTERAZIONE EDUCATORE-UTENTE**
Valuta come l'educatore ha gestito l'interazione, focalizzandoti su aspetti operativi:
- **qualita_comunicazione**: Chiarezza delle istruzioni, tono di voce, uso di supporti.
- **efficacia_strategie**: Quali tecniche educative sono state applicate e con quale risultato.
- **stato_emotivo**: Segnali osservabili (es. calma, pazienza, fretta) e il loro impatto sulla sessione.

---

**FASE 3: ANALISI DELL'EVENTO CRITICO (MODELLO 5W+1H)**

**IMPORTANTE**: Se nella trascrizione NON è presente un evento critico evidente (crisi, blocco, comportamento problematico), restituisci:
{
  "evento_presente": false,
  "analisi_evento_critico_5w1h": null
}

Se invece c'È un evento critico, **non rispondere tu alle domande**, ma fornisci il template come traccia di riflessione per l'educatore:
{
  "evento_presente": true,
  "analisi_evento_critico_5w1h": {
    "chi": "Chi era presente durante l'evento?",
    "cosa": "Cosa stava succedendo? Quale compito o regola era stato dato?",
    "dove": "Dove si è verificato l'evento? (spazio, rumori, stimoli presenti)",
    "quando": "Quando è successo? (es. durante una transizione, a fine attività)",
    "perche": "Quali potrebbero essere i fattori scatenanti? (es. richiesta troppo complessa, stanchezza, fame, dolore, cambiamento della routine)",
    "come": "Come si è manifestato il comportamento? (intensità, durata). Quali strategie ha provato l'educatore e con quale esito?"
  }
}

---

**FASE 4: SUGGERIMENTI PEDAGOGICI**

Basandoti sulle criticità emerse nei cluster e facendo riferimento al file `Strumenti_e_attivita.pdf`, fornisci suggerimenti brevi, concreti e attuabili subito.

1. **strategie_operative**: Per ogni cluster con livello 1 o 2, proponi una strategia specifica collegata. Usa questi template:
   - **Esempio Collegamento:** "Disregolazione -> Pausa Strutturata + Timer Visivo"
   - **Template Pausa Strutturata:** "Prevedi una pausa di [Durata], segnalandone inizio e fine con un [Segnale Visivo/Sonoro], in uno [Spazio Dedicato], e stabilendo una [Regola Semplice] per il rientro nell'attività."
   - **Template Istruzione Chiara:** "Fornisci una sola consegna per volta, usando un verbo d'azione (es. 'Prendi la palla') e attendi un check di comprensione prima di proseguire."
   - **Template Supporti Visivi:** "Utilizza [Tipo di Supporto, es. un'agenda visiva con la sequenza delle attività] per anticipare cosa succederà e ridurre l'ansia da attesa."

2. **supporti_comunicativi**: Se emergono bisogni comunicativi (cluster "Comunicazione Funzionale"), fornisci queste indicazioni:
   - **Prerequisito:** "Effettuare un assessment delle preferenze e dei motivatori dell'utente per identificare rinforzi efficaci."
   - **Strumento:** "Introdurre o rafforzare l'uso di un **quaderno di comunicazione** (cartaceo o digitale) come sistema dinamico e personalizzabile."
   - **Impostazione Pratica:** "Organizzare il quaderno con poche immagini per pagina (max 4), divise per aree tematiche (scuola, casa, bisogni), usando foto o icone a seconda del livello di astrazione dell'utente."
   - **Obiettivo:** "Creare numerose opportunità di scambio quotidiano (anche 30-40 al giorno) per consolidare l'uso dello strumento."

3. **suggerimenti_quaderno**: Se hai suggerito il quaderno di comunicazione, proponi una lista di 4-6 simboli pertinenti alla trascrizione da inserire. Esempio: ["Pausa", "Ancora", "Basta", "Aiuto", "Gioco", "Acqua"]

---

**FORMATO OUTPUT JSON:**
Restituisci l'analisi ESATTAMENTE in questo formato JSON (usa snake_case per le chiavi):
{
  "fase1_analisi_cluster": {
    "comunicazione_funzionale": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "autonomia_personale": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "gioco_e_partecipazione": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "socializzazione": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "gestione_disregolazione": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "tolleranza_frustrazione": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "pianificazione_spazio_temporale": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" },
    "regolazione_contesto": { "livello": null, "evidenze": [], "descrittori_osservati": [], "note": "" }
  },
  "fase2_analisi_interazione": {
    "qualita_comunicazione": "",
    "efficacia_strategie": "",
    "stato_emotivo": ""
  },
  "fase3_analisi_evento_critico": {
    "evento_presente": false,
    "analisi_evento_critico_5w1h": null
  },
  "fase4_suggerimenti_pedagogici": {
    "strategie_operative": [],
    "supporti_comunicativi": {},
    "suggerimenti_quaderno": []
  }
}
"""

    
  
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
            
            if analysis_text.strip().startswith("```json"):
                analysis_text = analysis_text.strip()[7:-3]

            elif analysis_text.strip().startswith("```"):
                analysis_text = analysis_text.strip()[3:-3]

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
    
    clusters = full_analysis.get("fase1_analisi_cluster", {})
    interaction = full_analysis.get("fase2_analisi_interazione", {})
    patterns = full_analysis.get("fase3_analisi_evento_critico", {})
    suggestions = full_analysis.get("fase4_suggerimenti_pedagogici", {})
    
    if not full_analysis:
        logger.warning("Nessuna analisi completa trovata nello stato.")

    return {
        "cluster_analysis": clusters,
        "interaction_analysis": interaction,
        "patterns_insights": patterns,
        "suggestions": suggestions,
        "action_plan": suggestions.get("strategie_operative", [])
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