#Questa parte è responsabile dell'estrazione del testo e delle informazioni sul
#layout utilizzando spaCyLayout

import spacy
from typing import Any
from spacy_layout import spaCyLayout
import logging

logger = logging.getLogger(__name__)

#Configurazione del logger
logging.basicConfig(level=logging.INFO)

#Funzione per inizializzare e restituire l'istanza di spacy con il componenete spacylayout
#Ci permette di analizzare la struttura del PDF (colonne, titoli, etc.)
def get_layout_extractor():
    #Inizializza un modello spaCy vuoto in italiano
    nlp = spacy.blank("it")
    #Aggiunge il componente spaCyLayout al modello
    layout_extractor = spaCyLayout(nlp)

    logger.info("Estrattore spaCyLayout per PDF inizializzato")
    return layout_extractor

#Funzione per caricare il documento da bytes
def load_pdf_from_bytes(pdf_bytes: bytes, layout_extractor: Any):
    try:
        #Chiama l'estrattore sui bytes del PDF
        doc = layout_extractor(pdf_bytes)
        logger.info("Estrazione del layout del PDF completata")
        return doc
    except Exception as e:
        logger.error(f"Errore durante il caricamento o l'estrazione del PDF: {e}")
        return None