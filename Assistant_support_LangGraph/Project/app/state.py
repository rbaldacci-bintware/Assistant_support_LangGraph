# app/state.py
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class GraphState(TypedDict):
    """
    Rappresenta lo stato del nostro grafo con routing dinamico.
    """
    # Campi base esistenti
    messages: Annotated[List[BaseMessage], add_messages]
    audio_file_paths: List[str] 
    transcript: str
    tenant_key: str
    project_name:Optional[str]

    # Campi per identificazione
    conversation_id: Optional[str]
    co_code: Optional[str]
    orgn_code: Optional[str]
    user_id: Optional[str]
    caller_id: Optional[str]
    scope: Optional[List[str]]
    
    # Campi per file storage
    location: Optional[str]
    inbound: Optional[str]
    outbound: Optional[str]
    
    # Risultati intermedi
    reconstruction: Optional[Dict[str, Any]]
    persistence_result: Optional[str]
    email_result: Optional[str]
    
    # Analisi AI
    full_analysis: Optional[Dict[str, Any]] 
    cluster_analysis: Optional[Dict[str, Any]]
    interaction_analysis: Optional[Dict[str, Any]]
    patterns_insights: Optional[Dict[str, Any]]
    suggestions: Optional[Dict[str, Any]]
    action_plan: Optional[Dict[str, Any]]
    
    # Metriche
    tokens_used: Optional[int]
    cost_usd: Optional[float]
    analysis_tokens_used: Optional[int]
    analysis_cost_usd: Optional[float]
    analysis_saved: Optional[bool]
    final_status: Optional[str]
    
    # Configurazione per i nodi
    config: Optional[Dict[str, Any]]
    
    # 🆕 NUOVI CAMPI per routing dinamico
    steps: Optional[List[str]]  # Lista ordinata dei nodi da eseguire
    current_step_index: Optional[int]  # Indice del passo corrente (0-based)
    skip_remaining: Optional[bool]  # Flag per interrompere l'esecuzione
    execution_trace: Optional[List[str]]  # Traccia dei nodi eseguiti
    error: Optional[str]  # Eventuale errore durante l'esecuzione

    
    id_assistito: Optional[str]
    
    # Campo per i risultati email
    email_result: Optional[str]
    email_response: Optional[str]
    email_error: Optional[str]

    knowledge_base_files: Optional[List[Dict[str, str]]] 