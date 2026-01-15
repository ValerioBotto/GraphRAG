from langgraph.graph import StateGraph, END
from agentLogic.state import AgentState
from agentLogic.nodes import node_router, node_retriever, node_generator, node_reranker, node_rewriter

workflow = StateGraph(AgentState)

#Aggiunta Nodi
workflow.add_node("rewriter", node_rewriter)
workflow.add_node("router", node_router)
workflow.add_node("retriever", node_retriever)
workflow.add_node("reranker", node_reranker)
workflow.add_node("generator", node_generator)

#Definizione Percorso
workflow.set_entry_point("rewriter")
workflow.add_edge("rewriter", "router")
workflow.add_edge("router", "retriever")
workflow.add_edge("retriever", "reranker")
workflow.add_edge("reranker", "generator") 
workflow.add_edge("generator", END)

app = workflow.compile()


    
