#Questo file definisce lo schema dei dati che passano tra i nodi

from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    query: str                                              #Domanda originale utente
    user_id: str
    filename: str                                           
    intent_data: dict                                       #Output di Mistral (route, entities, keywords)
    context_chunks: list
    final_answer: str

