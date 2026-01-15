#Questo documento incapsula la logica per l'estrazione delle NE e del testo strutturato

from gliner import GLiNER
import torch
import logging
from processingPdf.loader import get_layout_extractor, load_pdf_from_bytes
from processingPdf.logicSections import extract_logical_sections

logger = logging.getLogger(__name__)

class PDFExtractor:
    def __init__(self):
        self.layout_extractor = get_layout_extractor()

    def extract_sections(self, file_path: str):
        # Legge il file in bytes per spaCyLayout
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Carica il documento ed estrae il layout
        doc = load_pdf_from_bytes(pdf_bytes, self.layout_extractor)
        
        # Suddivide in sezioni logiche
        if doc:
            return extract_logical_sections(doc)
        return {}

class EntityExtractor:
    _model = None
    @staticmethod
    def get_model():
        if EntityExtractor._model is None:
            logger.info("Caricamento del modello GLiNER...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            EntityExtractor._model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1").to(device)
        return EntityExtractor._model
    
    @staticmethod
    def extract_ne(text: str):
        model = EntityExtractor.get_model()

        labels = [
    # --- GENERAL & IDENTIFIERS ---
    "Person", "Organization", "Location", "Date", "Time", 
    "Product", "Event", "Nationality", "Language",

    # --- BUROCRATICO, NORMATIVO & BANDI ---
    "Normative Reference",      # Articoli di legge, decreti, commi
    "Public Body",              # Enti pubblici (es. Ministero, Commissione Europea)
    "Deadline",                 # Scadenze per bandi, domande o pagamenti
    "Requirement",              # Requisiti di partecipazione o criteri di accesso
    "Amount",                   # Cifre monetarie, borse di studio, tasse
    "Evaluation Criteria",      # Criteri di punteggio o valutazione
    "Document Type",            # Es. ISEE, Marca da bollo, Certificato di laurea

    # --- TECNICO & MANUALE DI ISTRUZIONI ---
    "Component",                # Parti di macchinari o componenti hardware
    "Technical Specification",   # Es. 220V, 50Hz, risoluzione 4K, velocità rotazione
    "Error Code",               # Codici errore (es. E04, 404, Fault-01)
    "Safety Instruction",       # Avvertenze di sicurezza o pericoli
    "Tool",                     # Strumenti necessari (es. chiave inglese, cacciavite)
    "Operation Mode",           # Modalità operative (es. Standby, Manuale, Eco)

    # --- SCIENTIFICO, CHIMICO & FISICO ---
    "Scientific Term",          # Termini tecnici generali
    "Chemical Compound",        # Formule e nomi di sostanze (es. H2O, Glucosio)
    "Theory/Law",               # Leggi fisiche o teorie (es. Legge di Ohm, Relatività)
    "Measurement Unit",         # Unità di misura (es. Joule, Watt, Nanometri)
    "Phenomenon",               # Fenomeni naturali o reazioni (es. Ossidazione, Gravità)

    # --- MEDICO & CLINICO ---
    "Clinical Condition",       # Malattie, patologie o sintomi
    "Medical Parameter",        # Es. Glicemia, Pressione Arteriosa, Frequenza Cardiaca
    "Anatomical Structure",     # Organi, ossa, muscoli o tessuti
    "Drug/Medication",          # Nomi di farmaci o principi attivi
    "Diagnostic Test",          # Es. Risonanza Magnetica, Analisi del sangue

    # --- ACCADEMICO & SCOLASTICO ---
    "Academic Subject",         # Materie (es. Storia Moderna, Fisica Quantistica)
    "Exam/Test Name",           # Titoli di esami o test (es. Test TOLC, Prova Scritta)
    "Degree Course",            # Corsi di laurea o diplomi
    "Bibliographic Source",     # Citazioni, autori o titoli di testi universitari

    # --- STORICO & NARRATIVO (FANTASCIENZA) ---
    "Historical Period",        # Ere, secoli o movimenti (es. Illuminismo, Paleolitico)
    "Fictional Species",        # Es. Androidi, Alieni, Specie di fantasia
    "Technological Concept",    # Tecnologie immaginarie o concetti futuristici

    # --- QUANTITATIVO ---
    "Percentage",               # Percentuali e tassi
    "Quantity",                 # Quantità generiche non monetarie
    "Distance"                  # Distanze e lunghezze
]
        
        entities_found = model.predict_entities(text, labels, threshold=0.5)

        entities = []
        seen = set() # Per tracciare i duplicati nello stesso chunk

        for ent in entities_found:
            text_clean = ent["text"].strip().lower()
            label_clean = ent["label"].upper().replace(" ", "_")
            
            # Creiamo una chiave univoca per il set
            entity_key = (text_clean, label_clean)
            
            if entity_key not in seen:
                entities.append({
                    "text": text_clean,
                    "label": label_clean
                })
                seen.add(entity_key)
            
        return entities