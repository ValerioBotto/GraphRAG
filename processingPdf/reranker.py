import torch
import logging
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

class Reranker:
    def __init__(self, model_name="BAAI/bge-reranker-v2-m3"):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            #il CrossEncoder riceve coppie (domanda, chunk) e restituisce un punteggio
            self.model = CrossEncoder(model_name, device=device)
            logger.info(f"Re-ranker '{model_name}' caricato con successo.")
        except Exception as e:
            logger.error(f"Errore nel caricamento del Re-ranker: {e}")
            raise
    
    #riceve la query e la lista di chunks restituendo i top 5 (in questo caso) più rilevanti
    def rerank(self, query: str, documents: list, top_n: int = 5):
        if not documents:
            return []
        #coppie per il cross encoder
        pairs = [[query, doc] for doc in documents]
        #calcolo gli score di pertinenza
        scores = self.model.predict(pairs)
        #unisco i chunks ai loro score e li ordino
        scored_docs= sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:top_n]]