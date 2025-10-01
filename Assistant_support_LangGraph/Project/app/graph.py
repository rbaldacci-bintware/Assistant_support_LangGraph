# app/graph.py
import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from .state import GraphState

# Import dei nodi
from .graph_nodes import (
    conversation_reconstruction_node,
    persistence_node,
    email_node,
    analysis_node,
    suggestions_node,
    save_analysis_node
)

logger = logging.getLogger(__name__)

# ===== CONFIGURAZIONE =====

# Ordine di default per il flusso completo
DEFAULT_FLOW = [
    "reconstruct",
    "persist", 
    "email",
    "analyze",
    "suggest",
    "save_analysis",
    "email"
]

# Mapping nome nodo -> funzione
NODE_FUNCTIONS = {
    "reconstruct": conversation_reconstruction_node,
    "persist": persistence_node,
    "email": email_node,
    "analyze": analysis_node,
    "suggest": suggestions_node,
    "save_analysis": save_analysis_node
}

# Flussi predefiniti comuni
PRESET_WORKFLOWS = {
    "full": ["reconstruct", "persist", "email", "analyze", "suggest", "save_analysis"],
    "quick": ["reconstruct", "persist"],
    "analysis_only": ["analyze", "suggest", "save_analysis"],
    "reconstruct_only": ["reconstruct"],
    "persist_only": ["persist"],
    "email_only": ["email"],
    "no_email": ["reconstruct", "persist", "analyze", "suggest", "save_analysis"],
    "analysis_and_suggest": ["analyze", "suggest"],
    "with_email": ["reconstruct", "persist", "email"]
}

# ===== FUNZIONI DI ROUTING =====

def get_entry_point(state: GraphState) -> str:
    """
    Determina il punto di ingresso basato sullo state.
    """
    steps = state.get("steps", DEFAULT_FLOW)
    
    if not steps:
        logger.warning("Nessuno step definito, uso default flow")
        return DEFAULT_FLOW[0]
    
    # Se abbiamo già un indice, usa quello
    current_index = state.get("current_step_index", 0)
    if current_index < len(steps):
        return steps[current_index]
    
    return steps[0]

def route_to_next_step(state: GraphState) -> str:
    """
    Determina il prossimo nodo dopo l'esecuzione di uno step.
    """
    # Controlla se dobbiamo fermarci
    if state.get("skip_remaining"):
        logger.info("skip_remaining=True, termino il flusso")
        return END
    
    if state.get("error"):
        logger.error(f"Errore rilevato: {state['error']}, termino il flusso")
        return END
    
    # Ottieni la lista dei passi
    steps = state.get("steps", DEFAULT_FLOW)
    current_index = state.get("current_step_index", 0)
    
    # 🔧 FIX: NON incrementare qui! L'indice è già stato incrementato dal wrapper
    # Il current_index ora punta già al prossimo nodo da eseguire
    
    if current_index >= len(steps):
        logger.info(f"Completati tutti i {len(steps)} passi")
        return END
    
    next_node = steps[current_index]  # 🔧 Usa current_index direttamente!
    logger.info(f"Routing al prossimo nodo: {next_node} (step {current_index + 1}/{len(steps)})")
    return next_node

# ===== WRAPPER PER I NODI =====

def create_tracked_node(node_name: str, node_func):
    """
    Crea un wrapper che traccia l'esecuzione e gestisce gli errori.
    """
    def wrapped(state: GraphState) -> Dict[str, Any]:
        logger.info(f"🔷 Esecuzione nodo: {node_name}")
        
        # Inizializza execution_trace se non esiste
        trace = state.get("execution_trace", [])
        
        try:
            # Esegui il nodo originale
            result = node_func(state)
            
            # Aggiungi alla traccia
            trace_copy = trace.copy()
            trace_copy.append(node_name)
            result["execution_trace"] = trace_copy
            
            # Aggiorna l'indice
            current_index = state.get("current_step_index", 0)
            result["current_step_index"] = current_index + 1
            
            logger.info(f"✅ Nodo {node_name} completato con successo")
            return result
            
        except Exception as e:
            logger.error(f"❌ Errore nel nodo {node_name}: {str(e)}")
            
            # Ritorna stato con errore
            trace_copy = trace.copy()
            trace_copy.append(f"{node_name}[ERROR]")
            
            return {
                "error": f"Errore in {node_name}: {str(e)}",
                "execution_trace": trace_copy,
                "skip_remaining": True,
                "current_step_index": state.get("current_step_index", 0) + 1
            }
    
    return wrapped

# ===== COSTRUZIONE DEL GRAFO =====

def build_dynamic_graph():
    """
    Costruisce il grafo dinamico universale.
    """
    logger.info("🏗️ Costruzione del grafo dinamico...")
    
    workflow = StateGraph(GraphState)
    
    # Aggiungi tutti i nodi disponibili con tracking
    for node_name, node_func in NODE_FUNCTIONS.items():
        tracked_func = create_tracked_node(node_name, node_func)
        workflow.add_node(node_name, tracked_func)
        logger.info(f"  ✓ Aggiunto nodo: {node_name}")
    
    # Entry point condizionale - può andare a qualsiasi nodo
    workflow.add_conditional_edges(
        "__start__",
        get_entry_point,
        {node: node for node in NODE_FUNCTIONS.keys()}
    )
    
    # Ogni nodo decide dove andare dopo
    for node_name in NODE_FUNCTIONS.keys():
        workflow.add_conditional_edges(
            node_name,
            route_to_next_step,
            {
                **{other_node: other_node for other_node in NODE_FUNCTIONS.keys()},
                END: END
            }
        )
    
    compiled = workflow.compile()
    logger.info("✅ Grafo dinamico compilato con successo!")
    return compiled

# ===== HELPER FUNCTIONS =====

def prepare_workflow_steps(workflow_request: Optional[str | List[str]]) -> List[str]:
    """
    Prepara la lista di steps basata sulla richiesta.
    
    Args:
        workflow_request: Può essere:
            - None/vuoto -> usa DEFAULT_FLOW
            - string -> nome di un preset (es. "quick", "analysis_only")
            - List[str] -> lista custom di nodi
    """
    if not workflow_request:
        return DEFAULT_FLOW
    
    if isinstance(workflow_request, str):
        # È un preset?
        if workflow_request in PRESET_WORKFLOWS:
            return PRESET_WORKFLOWS[workflow_request]
        # Altrimenti interpretalo come singolo nodo
        return [workflow_request]
    
    if isinstance(workflow_request, list):
        # Valida che tutti i nodi esistano
        valid_steps = []
        for step in workflow_request:
            if step in NODE_FUNCTIONS:
                valid_steps.append(step)
            else:
                logger.warning(f"⚠️ Nodo '{step}' non esiste, verrà ignorato")
        return valid_steps
    
    return DEFAULT_FLOW

# ===== ESPORTA IL GRAFO =====

# Grafo dinamico principale
dynamic_graph = build_dynamic_graph()

# Per retrocompatibilità, mantieni anche i nomi vecchi
conversation_graph = dynamic_graph  # Alias per compatibilità
complete_graph = dynamic_graph      # Alias per compatibilità

print("✅ Sistema di routing dinamico pronto!")
print(f"   Nodi disponibili: {list(NODE_FUNCTIONS.keys())}")
print(f"   Workflow predefiniti: {list(PRESET_WORKFLOWS.keys())}")