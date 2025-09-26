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

# URL dell'API Google (esistente)
API_URL = os.getenv("GOOGLE_API_URL", "http://localhost:5020")

def conversation_reconstruction_node(state: GraphState) -> dict:
    """Nodo 1: Ricostruisce conversazione (ESISTENTE - modificato per nuovo flusso)"""
    print("--- NODO 1: RICOSTRUZIONE CONVERSAZIONE ---")
    
    # Se abbiamo location/inbound/outbound, usa AudioTools
    if state.get("location") and state.get("inbound") and state.get("outbound"):
        config = state.get("config", {})
        api_client = InternalApiClient(config)
        audio_tools = AudioTools(api_client)
        
        response = audio_tools.reconstruct_from_storage(
            location=state["location"],
            inbound_filename=state["inbound"],
            outbound_filename=state["outbound"],
            tenant_key=state["tenant_key"]
        )
        
        return {
            "transcript": response.reconstructedTranscript,
            "reconstruction": response.dict(),
            "tokens_used": response.usage.tokens,
            "cost_usd": response.usage.costUsd
        }
    
    # Altrimenti usa il metodo esistente con file_paths
    elif len(state.get("audio_file_paths", [])) == 2:
        tenant_key = state.get("tenant_key")
        if not tenant_key:
            raise ValueError("tenant_key non trovato")
        
        params = {"tenant_key": tenant_key}
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
            transcript = data["reconstructedTranscript"]
            
            return {
                "transcript": transcript,
                "reconstruction": data,
                "tokens_used": data.get("usage", {}).get("tokens", 0),
                "cost_usd": data.get("usage", {}).get("costUsd", 0.0)
            }
    
    raise ValueError("Configurazione non valida per ricostruzione")

def persistence_node(state: GraphState) -> dict:
    """Nodo 2: Salva trascrizione nel database"""
    print("--- NODO 2: PERSISTENZA ---")
    
    if not state.get("conversation_id"):
        logger.warning("conversation_id non presente, skip persistenza")
        return {"persistence_result": "SKIPPED"}
    
    config = state.get("config", {})
    api_client = InternalApiClient(config)
    persistence_client = PersistenceClient(api_client)
    
    result = persistence_client.save_conversation(
        conversation_id=state["conversation_id"],
        transcript=state["transcript"]
    )
    
    logger.info(f"Persistenza: Status={result.status}, Id={result.id}")
    
    return {"persistence_result": f"{result.status}:{result.id}"}

def email_node(state: GraphState) -> dict:
    """Nodo 3: Invio email (stub)"""
    print("--- NODO 3: EMAIL ---")
    
    # Come nel C#, non implementato
    logger.info("Email node chiamato ma non implementato")
    
    return {"email_result": "NOT_IMPLEMENTED"}


def analysis_node(state: GraphState) -> dict:
    """Nodo 4: Analisi AI tramite API HTTP (modificato per compatibilità JSON)"""
    print("--- NODO 4: ANALISI AI ---")

    # Il prompt rimane lo stesso, ma lo useremo per il payload JSON
    analysis_prompt = """
          
          Sei un analista esperto in ambito educativo e terapeutico. Ti fornisco tre documenti con ruoli specifici:

1.  **Documenti di Riferimento (Knowledge Base):**
    * `Documento_di_Pianificazione_per_ORA.pdf`
    * `Strumenti_e_attivita.pdf`
    Questi due file costituiscono la tua unica fonte di conoscenza per i criteri di valutazione, le definizioni e gli strumenti da consigliare. Devi basare la tua analisi esclusivamente su quanto descritto in questi documenti.

2.  **Documento da Analizzare:**
    * `Trascrizione.txt`
    Questo file contiene la trascrizione della sessione che devi analizzare.

**Il tuo compito è il seguente:**
Analizza il file `Trascrizione.txt`. Per ogni fase dell'analisi, devi applicare i concetti, le strategie e le scale di valutazione definite nei due documenti di riferimento. Puoi usare la tua conoscenza generale per arricchire il linguaggio e la struttura della risposta, ma ogni giudizio, valutazione e suggerimento deve essere direttamente collegato alle informazioni contenute nei file della knowledge base.

Ora, procedi con l'analisi e genera un output in formato JSON strutturato come segue:

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

    # MODIFICA 1: Rimosso il codice per multipart/form-data.
    # Non creiamo più file in memoria o form_data.

    # MODIFICA 2: Creiamo il payload JSON che l'API C# si aspetta.
    # Questo deve corrispondere esattamente alla struttura del comando cURL.
    json_payload = {
        "prompt": analysis_prompt,
        "files": [
            # I file di knowledge base
            {
              "location": "analisi",
              "fileName": "Documento_di_Pianificazione_per_ORA.pdf"
            },
            {
              "location": "analisi",
              "fileName": "Strumenti_e_attivita.pdf"
            },
            # Aggiungiamo la trascrizione come un altro file da recuperare
            {
              "location": "analisi", # Assumendo che la trascrizione sia nello stesso percorso
              "fileName": "Trascrizione.txt"
            }
        ],
        "geminiModelName": "gemini-2.5-pro", # o state.get('modelName', 'gemini-2.5-pro')
        "tenantKey": state.get('tenant_key', 'COESO_INTERV')
    }

    try:
        # MODIFICA 3: Aggiornata la chiamata a requests.post()
        # Usiamo il parametro 'json' per inviare application/json
        # e aggiorniamo l'URL.
        response = requests.post(
            f"{API_URL}/api/GeminiTextGeneration/analyze-dynamic",
            json=json_payload, # requests imposta automaticamente Content-Type: application/json
            headers={'Accept': 'application/json'}, # È buona norma specificare cosa accettiamo
            timeout=180 # Aumentato per analisi complesse
        )

        if response.status_code == 200:
            # MODIFICA 4: Aggiornata la gestione della risposta
            # L'API C# ora inoltra l'intera risposta di Gemini.
            gemini_response = response.json()

            # Estraiamo il testo JSON dall'interno della struttura di Gemini
            analysis_text = gemini_response['candidates'][0]['content']['parts'][0]['text']
            analysis = json.loads(analysis_text) # Deserializziamo la stringa JSON

            # Estraiamo i dati di utilizzo dalla nuova struttura
            usage = gemini_response.get('usageMetadata', {})
            tokens_used = usage.get('totalTokenCount', 0)
            # Nota: il costo non è fornito direttamente da Gemini, dovrai calcolarlo tu.
            cost_usd = 0.0 # Placeholder per il costo

            logger.info(f"Analisi completata. Tokens: {tokens_used}")

            # Ritorna i risultati estratti dalla nuova struttura
            return {
                "cluster_analysis": analysis.get("fase1_analisi_cluster", {}),
                "interaction_analysis": analysis.get("fase2_analisi_interazione", {}),
                "patterns_insights": analysis.get("fase3_identificazione_pattern", {}),
                # Aggiungiamo anche la fase 4 per usarla nel nodo successivo
                "suggestions_payload": analysis.get("fase4_generazione_suggerimenti", {}),
                "analysis_tokens_used": tokens_used,
                "analysis_cost_usd": cost_usd
            }

        else:
            logger.error(f"Errore API: Status {response.status_code}, Response: {response.text}")
            return {"error": f"API error: {response.status_code}", "details": response.text}

    except Exception as e:
        logger.error(f"Errore durante la chiamata di analisi: {str(e)}")
        return {"error": str(e)}
    
    
def suggestions_node(state: GraphState) -> dict:
    """Nodo 5: Genera suggerimenti basati sull'analisi"""
    print("--- NODO 5: SUGGERIMENTI ---")
    
    # Recupera l'analisi dallo stato
    clusters = state.get("cluster_analysis", {})
    interaction = state.get("interaction_analysis", {})
    patterns = state.get("patterns_insights", {})
    
    # Se non hai analisi, genera suggerimenti base
    if not clusters:
        return {
            "suggestions": {"note": "Analisi non disponibile"},
            "action_plan": {"note": "Piano non generato"}
        }
    
    # Genera suggerimenti basati sull'analisi
    suggestions = {
        "report_sintesi": {
            "punti_forza": [],
            "aree_miglioramento": [],
            "eventi_salienti": []
        },
        "suggerimenti": {
            "strategie_alternative": [],
            "strumenti_consigliati": [],
            "approcci_specifici": []
        },
        "piano_prossima_sessione": {
            "obiettivi_smart": [],
            "checklist_osservazioni": [],
            "attivita_proposte": []
        }
    }
    
    # Analizza i cluster per determinare punti forza e aree di miglioramento
    for cluster_name, cluster_data in clusters.items():
        if isinstance(cluster_data, dict):
            score = cluster_data.get("score", 0)
            evidenze = cluster_data.get("evidenze", "")
            
            if score >= 3:
                suggestions["report_sintesi"]["punti_forza"].append(
                    f"{cluster_name.replace('_', ' ').title()}: {evidenze[:100]}"
                )
            else:
                suggestions["report_sintesi"]["aree_miglioramento"].append(
                    f"{cluster_name.replace('_', ' ').title()} (score: {score}/4)"
                )
                
                # Suggerisci strategie specifiche per cluster bassi
                if cluster_name == "comunicazione_funzionale" and score <= 2:
                    suggestions["suggerimenti"]["strategie_alternative"].extend([
                        "Implementare supporti visivi per la comunicazione (PECS, tabelle CAA)",
                        "Utilizzare timer visivi per strutturare le attività",
                        "Introdurre routine di richiesta strutturata"
                    ])
                    suggestions["suggerimenti"]["strumenti_consigliati"].append(
                        "App di comunicazione aumentativa (es. Proloquo2Go, ARASAAC)"
                    )
                
                if cluster_name == "autonomia_personale" and score <= 2:
                    suggestions["suggerimenti"]["strategie_alternative"].extend([
                        "Suddividere i compiti in step più piccoli e gestibili",
                        "Utilizzare checklist visive per le routine quotidiane",
                        "Implementare un sistema di rinforzo token economy"
                    ])
    
    # Usa i pattern insights per suggerimenti specifici
    if patterns:
        correlazioni = patterns.get("correlazioni", [])
        segnali_deboli = patterns.get("segnali_deboli", [])
        
        for correlazione in correlazioni[:2]:  # Prime 2 correlazioni
            suggestions["report_sintesi"]["eventi_salienti"].append(correlazione)
        
        for segnale in segnali_deboli[:2]:  # Primi 2 segnali
            # Genera un obiettivo basato sul segnale
            if "calcolo" in str(segnale).lower():
                suggestions["piano_prossima_sessione"]["obiettivi_smart"].append(
                    "Incrementare gradualmente la complessità degli esercizi di calcolo del 20%"
                )
                suggestions["piano_prossima_sessione"]["attivita_proposte"].append(
                    "Sessione di calcolo strutturato con difficoltà progressiva (15 min)"
                )
            
            if "social" in str(segnale).lower() or "interazione" in str(segnale).lower():
                suggestions["piano_prossima_sessione"]["obiettivi_smart"].append(
                    "Completare almeno 2 role-playing di interazione sociale"
                )
                suggestions["piano_prossima_sessione"]["attivita_proposte"].append(
                    "Role-playing guidato con supporto visivo (10 min)"
                )
    
    # Aggiungi approcci basati sulla qualità dell'interazione
    if interaction.get("efficacia_strategie"):
        suggestions["suggerimenti"]["approcci_specifici"].append(
            "Mantenere le strategie attuali che si sono dimostrate efficaci"
        )
    
    # Aggiungi sempre alcune osservazioni standard
    suggestions["piano_prossima_sessione"]["checklist_osservazioni"].extend([
        "Numero di richieste spontanee",
        "Tempo di permanenza sul compito",
        "Frequenza comportamenti problema",
        "Efficacia dei prompt utilizzati"
    ])
    
    # Se non ci sono suggerimenti specifici, aggiungi dei default
    if not suggestions["suggerimenti"]["strategie_alternative"]:
        suggestions["suggerimenti"]["strategie_alternative"] = [
            "Continuare con l'approccio attuale monitorando i progressi"
        ]
    
    if not suggestions["piano_prossima_sessione"]["obiettivi_smart"]:
        suggestions["piano_prossima_sessione"]["obiettivi_smart"] = [
            "Mantenere il livello attuale di performance per consolidare gli apprendimenti"
        ]
    
    return {
        "suggestions": suggestions,
        "action_plan": suggestions.get("piano_prossima_sessione", {})
    }

def save_analysis_node(state: GraphState) -> dict:
    """Nodo 6: Salva analisi"""
    print("--- NODO 6: SALVATAGGIO ANALISI ---")
    
    # Qui salveresti le analisi nel tuo sistema
    logger.info(f"Salvando analisi per conversazione {state.get('conversation_id', 'N/A')}")
    
    return {
        "analysis_saved": True,
        "final_status": "COMPLETED"
    }