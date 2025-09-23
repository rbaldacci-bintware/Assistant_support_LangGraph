# graph.py
from langgraph.graph import StateGraph, START
from .state import GraphState
from .graph_nodes import conversation_reconstruction_node  # ← SOLO questa importazione

# --- GRAFO PER LA RICOSTRUZIONE DELLA CONVERSAZIONE ---
conversation_workflow = StateGraph(GraphState)
conversation_workflow.add_node("conversation_reconstruction", conversation_reconstruction_node)
conversation_workflow.add_edge(START, "conversation_reconstruction")
conversation_workflow.set_finish_point("conversation_reconstruction")
conversation_graph = conversation_workflow.compile()
print("Grafo per ricostruzione conversazione compilato con successo!")