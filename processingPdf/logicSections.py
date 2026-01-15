#Questa parte si occupa di suddividere il documento processato in sezioni logiche
#(capitoli, sottosezioni, etc.) sfruttando le etichette di layout.

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

#Suddivide il documneto spaCy in sezioni logiche basandosi sulle etichette di layout. Il "doc" è il documento spaCy processato da load_pdf_from_bytes
#Ritorna un dizionario dove la chiave è il titolo della sezione e il valore è il testo associato
def extract_logical_sections(doc: Any) -> Dict[str, Any]:
    sections = {}
    #Questo è un titolo segnaposto per eventuale contenuto iniziale non etichettato da un header
    current_title = "preambolo_documento"
    sections[current_title] = ""

    #Etichette che indicano l'inizio di una NUOVA SEZIONE LOGICA
    SECTION_LABELS = ("SECTION_HEADER", "TITLE", "BOLD", "BOLD_CAPTION")

    #Etichette di Contenuto (da trattare come corpo testuale)
    CONTENT_LABELS = ("TEXT", "LIST", "PARAGRAPH")

    if not hasattr(doc, 'spans') or not doc.spans.get ("layout"):
        if hasattr(doc, 'text') and doc.text.strip():
            logger.warning("Nessun layout distinto trovato, restituisco il documento completo come sezione unica.")
            return {"documento_completo": doc.text.strip()}
        return {}
    
    #Itera su tutti gli span etichettati
    for span in doc.spans.get("layout", []):
        label = span.label_.upper()
        span_text = span.text.strip()

        if not span_text:
            continue
        
        #1. Identificazione e cambio di sezione
        if label in SECTION_LABELS:
            potential_title = span_text.lower()
            #Assicuriamo l'unicità e un minimo di lunghezza
            if len(potential_title) > 3 and potential_title not in sections:
                current_title = potential_title
                sections[current_title] = ""
            elif current_title in sections:
                #Se il titolo non cambia, aggiungiamo il testo (utile per titoli multi-linea)
                sections[current_title] += span_text + "\n"
        
        #2. Gestione Esplicita di informazioni tabulari e immagini
        elif label == "TABLE_CAPTION":
            #Usiamo la caption come nuovo titolo di sezione temporaneo
            current_title = f"tabella: {span_text.lower()[:100]}"
            if current_title not in sections:
                sections[current_title] = span_text + "\n"

        elif label == "FIGURE_CAPTION":
            #Usiamo la caption come nuovo titolo di sezione temporaneo (per immagini ora)
            current_title = f"figura: {span_text.lower()[:100]}"
            if current_title not in sections:
                sections[current_title] = span_text + "\n"
        
        #3. Gestione del Testo del Corpo/Contenuto
        elif label in CONTENT_LABELS:
            #Aggiunge il testo sotto la sezione corrente o preambolo
            sections[current_title] += span_text + "\n"
        
        #4. Blocchi di contenuto generici (Es. Table o Figure senza caption)
        elif label in ("TABLE", "FIGURE"):
            # Se la label è TABLE o FIGURE e non abbiamo ancora una caption, 
            # usiamo un titolo generico per non perdere il testo.
            if "tabella:" not in current_title and "figura:" not in current_title:
                 current_title = f"blocco_generico_{label.lower()}"
                 if current_title not in sections:
                     sections[current_title] = ""
            sections[current_title] += span_text + "\n"
        
    #Pulisce le sezioni vuote e rimuove spazi iniziali/finali
    cleaned_sections = {k: v.strip() for k, v in sections.items() if v.strip()}

    #Gestisce il caso di documenti con molto rumore o layout non convenzionale
    if not cleaned_sections and hasattr(doc, 'text') and doc.text.strip():
        logger.warning("Suddivisione per layout fallita, ritorno il documento completo come sezione unica.")
        return {"documento_completo": doc.text.strip()}
        
    logger.info(f"Documento suddiviso in {len(cleaned_sections)} sezioni logiche.")
    return cleaned_sections