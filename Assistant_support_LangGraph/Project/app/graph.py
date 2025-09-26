# app/graph.py
from langgraph.graph import StateGraph, START, END
from .state import GraphState
from .graph_nodes import conversation_reconstruction_node

# Importa TUTTI i nodi necessari per il grafo completo
try:
    from .graph_nodes import (
        persistence_node,
        email_node,
        analysis_node,
        suggestions_node,
        save_analysis_node
    )
    COMPLETE_NODES_AVAILABLE = True
except ImportError:
    COMPLETE_NODES_AVAILABLE = False
    print("⚠️ Nodi completi non disponibili, usando solo ricostruzione base")

# --- GRAFO SEMPLICE (esistente) ---
conversation_workflow = StateGraph(GraphState)
conversation_workflow.add_node("conversation_reconstruction", conversation_reconstruction_node)
conversation_workflow.add_edge(START, "conversation_reconstruction")
conversation_workflow.set_finish_point("conversation_reconstruction")
conversation_graph = conversation_workflow.compile()
print("✅ Grafo semplice compilato!")

# --- GRAFO COMPLETO (nuovo) - solo se i nodi sono disponibili ---
if COMPLETE_NODES_AVAILABLE:
    complete_workflow = StateGraph(GraphState)
    
    # Aggiungi tutti i nodi
    complete_workflow.add_node("reconstruct", conversation_reconstruction_node)
    complete_workflow.add_node("persist", persistence_node)
    complete_workflow.add_node("email", email_node)
    complete_workflow.add_node("analyze", analysis_node)
    complete_workflow.add_node("suggest", suggestions_node)
    complete_workflow.add_node("save_analysis", save_analysis_node)
    
    # Definisci il flusso
    complete_workflow.add_edge(START, "reconstruct")
    complete_workflow.add_edge("reconstruct", "persist")
    complete_workflow.add_edge("persist", "email")
    complete_workflow.add_edge("email", "analyze")
    complete_workflow.add_edge("analyze", "suggest")
    complete_workflow.add_edge("suggest", "save_analysis")
    complete_workflow.add_edge("save_analysis", END)
    
    complete_graph = complete_workflow.compile()
    print("✅ Grafo completo compilato!")
else:
    complete_graph = None