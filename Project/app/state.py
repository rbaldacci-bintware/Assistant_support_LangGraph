#state.py
from typing import Annotated, List, TypedDict
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