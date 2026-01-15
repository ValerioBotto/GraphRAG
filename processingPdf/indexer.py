#Questo file è responsabile di due compiti principali: caricare il modello di embedding 
#e orchestrare l'indicizzazione completa su Neo4j

import logging
import torch
from typing import List
from langchain_core.documents import Document as LangchainDocument
from sentence_transformers import SentenceTransformer
from processingPdf.extractor import EntityExtractor
from dotenv import load_dotenv
import os

from db.graph_db import GraphDB

logger = logging.getLogger(__name__)

load_dotenv()

#Gestisce il caricamento del modello di emedding e l'indicizzazione dei chunk in Neo4j
class Indexer:
    def __init__(self):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Caricamento del modello di embedding sul dispositivo: {device}")
            #sentence-transformers gestisce l'ottimizzazione del caricamento
            self.embedding_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL_NAME"), device=device)
            self.embedding_dimensions = self.embedding_model.get_sentence_embedding_dimension()
            logger.info(f"Modello di embedding '{os.getenv('EMBEDDING_MODEL_NAME')}' caricato con {self.embedding_dimensions} dimensioni.")
        except Exception as e:
            logger.error(f"Errore durante il caricamento del modello di embedding: {e}")
            raise e

    #Genera l'embedding vettoriale per un dato testo. Aggiungo un cast a List[float] per compatibilità con Neo4j
    def generate_embeddings(self, text:str) -> List[float]:
        return self.embedding_model.encode(text).tolist()
    
    #Orchestra l'indicizzazione dei chunk in Neo4j, gestendo la creazione del documento, dell'utente, del link e dell'inidice vettoriale
    def index_chunks_to_neo4j(self, filename: str, chunks: list, user_id: str, lang: str = "it"):
        if not chunks:
            logger.warning("Nessun chunk fornito per l'indicizzazione.")
            return
        
        graph_db = None
        try:
            # 1. Inizializzo la connessione a Neo4j
            graph_db = GraphDB()

            # 2. Creazione/Aggiornamento nodi user e document
            graph_db.create_user_node(user_id)
            graph_db.create_document_node(filename)
            graph_db.link_user_to_document(user_id, filename)

            # 3. Creazione indice vettoriale (se non esiste)
            graph_db.create_vector_index(
                index_name="chunk_embeddings_index",
                node_label="Chunk",
                property_name="embedding",
                vector_dimensions=self.embedding_dimensions
            )

            # 4. Inserimento chunk ed embedding
            for i, chunk in enumerate(chunks):
                content = chunk.page_content
                metadata = chunk.metadata
                
                # Ho deciso di assicurarmi che esista sempre un chunk_id valido
                chunk_id = metadata.get("chunk_id") or f"{filename}_{i}"

                # Genero l'embedding per il contenuto corrente
                embedding = self.generate_embeddings(content)

                # Ho deciso di implementare un controllo di sicurezza bloccante: 
                # se l'embedding è vuoto o ha dimensioni errate, salto l'inserimento per evitare nodi "sporchi"
                if not embedding or len(embedding) != self.embedding_dimensions:
                    logger.error(f"FALLIMENTO CRITICO: Ho rilevato un embedding non valido per il chunk {chunk_id}. Dimensione: {len(embedding) if embedding else 0}")
                    continue

                # Salvo il chunk, l'embedding e i metadati in Neo4j
                graph_db.add_chunk_to_document(filename, chunk_id, content, embedding, metadata)
                logger.debug(f"Ho indicizzato con successo il chunk '{chunk_id}' per il file '{filename}'.")

                # Estrazione e collegamento delle entità tramite GLiNER
                try:
                    entities = EntityExtractor.extract_ne(content)
                    for ent in entities:
                        graph_db.add_entity_to_chunk(ent["text"], ent["label"], chunk_id)
                except Exception as ne_e:
                    # Ho deciso di loggare l'errore delle entità come warning per non bloccare l'intera pipeline
                    logger.warning(f"Non sono riuscito a estrarre entità per il chunk {chunk_id}: {ne_e}")
            
            logger.info(f"Ho completato l'indicizzazione di {len(chunks)} chunk per il file '{filename}'.")
        
        except Exception as e:
            logger.error(f"Ho riscontrato un errore fatale durante l'indicizzazione in Neo4j per '{filename}': {e}")
            raise
        finally:
            if graph_db:
                graph_db.close()
            
    # Metodo coordinatore per processare il file fisico
    def index_pdf(self, file_path: str, user_id: str):
        # Import locali per gestire la pipeline
        from processingPdf.extractor import PDFExtractor 
        from processingPdf.chunker import Chunker
        
        filename = os.path.basename(file_path)
        
        # 1. Estrazione del testo strutturato dal PDF
        extractor = PDFExtractor() 
        sections = extractor.extract_sections(file_path) 
        
        # 2. Suddivisione delle sezioni in chunk
        chunker = Chunker()
        chunks = chunker.create_chunks(sections, filename)
        
        # 3. Indicizzazione finale su Neo4j 
        self.index_chunks_to_neo4j(filename, chunks, user_id)