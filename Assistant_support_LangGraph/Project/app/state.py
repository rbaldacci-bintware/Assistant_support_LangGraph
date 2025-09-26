#state.py
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Usiamo TypedDict per avere un controllo sui tipi e un codice più leggibile.
# Questo stato conterrà:
# - messages: La cronologia della conversazione (best practice per agenti).
# - audio_file_path: Il percorso temporaneo del file audio caricato.
# - transcript: La trascrizione finale elaborata dal modello.

class GraphState(TypedDict):
    """
    Rappresenta lo stato del nostro grafo.
    
    Attributes:
        messages: La cronologia dei messaggi.
        audio_file_paths: Lista dei percorsi dei file audio da processare.
        transcript: La trascrizione risultante.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    audio_file_paths: List[str] 
    transcript: str
    tenant_key: str

    conversation_id: Optional[str]
    co_code: Optional[str]
    orgn_code: Optional[str]
    user_id: Optional[str]
    caller_id: Optional[str]
    scope: Optional[List[str]]
    location: Optional[str]
    inbound: Optional[str]
    outbound: Optional[str]
    
    # Risultati intermedi
    reconstruction: Optional[Dict[str, Any]]
    persistence_result: Optional[str]
    email_result: Optional[str]
    
    # Analisi AI
    cluster_analysis: Optional[Dict[str, Any]]
    interaction_analysis: Optional[Dict[str, Any]]
    patterns_insights: Optional[Dict[str, Any]]
    suggestions: Optional[Dict[str, Any]]
    action_plan: Optional[Dict[str, Any]]
    
    # Metriche
    tokens_used: Optional[int]
    cost_usd: Optional[float]
    analysis_saved: Optional[bool]
    final_status: Optional[str]
    
    # Configurazione per i nodi
    config: Optional[Dict[str, Any]]