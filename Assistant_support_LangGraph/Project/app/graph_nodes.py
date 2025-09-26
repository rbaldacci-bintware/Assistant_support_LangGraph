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
    """Nodo 4: Analisi AI tramite API HTTP"""
    print("--- NODO 4: ANALISI AI ---")
    
    import io
    import requests
    
    # Prepara il prompt per l'analisi
    analysis_prompt = f"""
    Analizza questa trascrizione nel contesto di supporto disabilità.
    
    TRASCRIZIONE: {state['transcript'][:5000]}  # Limita per token
    
    Genera JSON con:
    {{
        "clusters": {{
            "comunicazione_funzionale": {{"score": 1-4, "evidenze": "..."}},
            "autonomia_personale": {{"score": 1-4, "evidenze": "..."}}
        }},
        "interazione": {{
            "qualita_comunicazione": "...",
            "efficacia_strategie": "..."
        }},
        "patterns": {{
            "correlazioni": [],
            "segnali_deboli": []
        }}
    }}
    
    Rispondi SOLO con JSON valido.
    """
    
    # Prepara la trascrizione come file in memoria
    transcript_file = io.BytesIO(state['transcript'].encode('utf-8'))
    
    # Prepara i parametri multipart
    files = [
        ('fileToAnalyze', ('transcript.txt', transcript_file, 'text/plain'))
    ]
    
    # Prepara i dati del form
    form_data = []
    form_data.append(('tenantKey', state.get('tenant_key', 'COESO_INTERV')))
    form_data.append(('prompt', analysis_prompt))
    form_data.append(('modelName', 'gemini-2.5-pro'))
    
    # Aggiungi i knowledge file paths
    knowledge_paths = [
        'gs://bucket_analyses/coeso-ora-docs/Strumenti e attività.pdf',
        'gs://bucket_analyses/coeso-ora-docs/Documento di Pianificazione per ORA.pdf'
    ]
    
    for path in knowledge_paths:
        form_data.append(('knowledgeFilePaths', path))
    
    try:
        # Fai la chiamata all'API
        response = requests.post(
            f"{API_URL}/api/GeminiTextGeneration/analyze-with-knowledge-base",
            data=form_data,
            files=files,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # L'API restituisce un oggetto con campo 'analysis' che contiene una stringa JSON
            if isinstance(result, dict) and "analysis" in result:
                analysis_text = result.get('analysis', '{}')
                analysis = json.loads(analysis_text)
            else:
                # Fallback per altri formati di risposta
                analysis = result if isinstance(result, dict) else {}
            
            # Log dei token usati se disponibili
            if result.get('usage'):
                logger.info(f"Analisi completata. Tokens: {result['usage'].get('tokens', 0)}, "
                          f"Costo: ${result['usage'].get('costUsd', 0.0)}")
            
            # Ritorna i risultati con i nomi corretti per il mapping
            return {
                "cluster_analysis": analysis.get("clusters", {}),
                "interaction_analysis": analysis.get("interazione", {}),
                "patterns_insights": analysis.get("patterns", {}),
                "analysis_tokens_used": result.get('usage', {}).get('tokens', 0) if isinstance(result, dict) else 0,
                "analysis_cost_usd": result.get('usage', {}).get('costUsd', 0.0) if isinstance(result, dict) else 0.0
            }
            
        else:
            logger.error(f"Errore API: Status {response.status_code}, Response: {response.text}")
            return {
                "cluster_analysis": {},
                "interaction_analysis": {},
                "patterns_insights": {},
                "error": f"API error: {response.status_code}"
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"Errore parsing JSON: {str(e)}")
        return {
            "cluster_analysis": {},
            "interaction_analysis": {},
            "patterns_insights": {},
            "error": f"JSON parsing error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Errore analisi AI: {str(e)}")
        return {
            "cluster_analysis": {},
            "interaction_analysis": {},
            "patterns_insights": {},
            "error": str(e)
        }
    
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