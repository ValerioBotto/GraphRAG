# Questa parte si occupa di segmentare il testo delle sezioni in blocchi più piccoli (chunks)
# adatti alla ricerca vettoriale, utilizzando RecursiveCharacterTextSplitter (RCTS) di LangChain.

import logging
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

class Chunker:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        # Inizializzazione splitter
        # Usa il RCTS per suddividere il testo usando una lista di separatori (newline, doppia newline, spazi, etc)
        # preservando la coerenza testuale e semantica
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
            length_function=len,
        )

    # Questa funzione divide le sezioni logiche del documento in chunk di dimensione fissa con sovrapposizione
    # Tra gli args abbiamo:
    # sections: Dizionario con titoli di sezione e relativi testi
    # filename: Nome del file PDF originale (usato per i metadati)
    # Restituisce una lista di oggetti Document di LangChain, ciascuno contenente un chunk e i suoi metadati
    def create_chunks(self, sections: Dict[str, str], filename: str) -> List[Document]:
        
        # Gestione input
        if not sections:
            logger.warning("Nessuna sezione fornita per il chunking")
            return []
        
        all_chunks: List[Document] = []

        # Iterazione e Chunking
        for section_title, section_text in sections.items():
            if not section_text.strip():
                logger.debug(f"Salto sezione vuota: '{section_title}'")
                continue
            
            try:
                # Normalizzo il testo in lowercase
                section_text = section_text.lower()
                
                # 1. Divide il testo della sezione (lo splitter accetta una lista di testi)
                chunks_for_section = self.text_splitter.create_documents([section_text])
                
                # 2. Aggiunge metadati a ciascun chunk
                for i, chunk in enumerate(chunks_for_section):
                    # Metadato 'source' per il nome del documento
                    chunk.metadata["source"] = filename
                    
                    # Metadato 'section' per il titolo logico (per il RAG)
                    chunk.metadata["section"] = section_title
                    
                    # ID univoco per il chunk (combinazione di filename, sezione e indice)
                    # Normalizziamo il titolo della sezione per un ID più pulito e sicuro
                    clean_section_id = section_title.lower().replace(' ', '_').replace('/', '_').replace(':', '_')
                    chunk.metadata["chunk_id"] = f"{filename}_{clean_section_id}_{i}"
                    
                    all_chunks.append(chunk)
                
                logger.debug(f"Sezione '{section_title}' divisa in {len(chunks_for_section)} chunk.")
            
            except Exception as e:
                logger.error(f"Errore durante il chunking della sezione '{section_title}': {e}")

        logger.info(f"Totale {len(all_chunks)} chunk generati.")
        return all_chunks