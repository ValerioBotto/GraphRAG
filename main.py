import streamlit as st
import os
import logging
from processingPdf.loader import get_layout_extractor
from processingPdf.logicSections import extract_logical_sections
from processingPdf.chunker import split_sections_into_chunks
from processingPdf.indexer import Indexer
from db.graph_db import GraphDB
from dotenv import load_dotenv

# Importazione del workflow LangGraph
from agentLogic.graph import app as rag_app

# Configurazione Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

st.set_page_config(page_title="RAG Chatbot - PDF", layout="wide")

# Inizializzazione componenti nel session_state
if "indexer" not in st.session_state:
    st.session_state.indexer = Indexer()
if "layout_extractor" not in st.session_state:
    st.session_state.layout_extractor = get_layout_extractor()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_ready" not in st.session_state:
    st.session_state.pdf_ready = False

st.title("RAG Chatbot")
st.markdown("Carica un PDF per indicizzarlo su Neo4j e iniziare a chattare.")

# --- SIDEBAR: CARICAMENTO E INDICIZZAZIONE ---
with st.sidebar:
    st.header("Profilo Utente")
    
    user_name_input = st.text_input("Ciao! Inserisci il tuo nome/nickname", placeholder="es. Laura")
    user_id_clean = user_name_input.strip().lower().replace(" ", "_")
    
    if not user_id_clean:
        st.warning("Inserisci un nome utente per procedere.")
    else:
        st.success(f"Loggato come: {user_id_clean}")
    
    st.divider()
    st.header("Caricamento PDF")
    uploaded_file = st.file_uploader("Scegli un file PDF", type="pdf")
    
    if uploaded_file is not None and user_id_clean:
        if st.button("Indicizza Documento"):
            with st.spinner("Elaborazione in corso..."):
                try:
                    file_bytes = uploaded_file.getvalue()
                    filename = uploaded_file.name
                    
                    doc = st.session_state.layout_extractor(file_bytes)
                    sections = extract_logical_sections(doc)
                    chunks = split_sections_into_chunks(sections, filename)
                    
                    st.session_state.indexer.index_chunks_to_neo4j(filename, chunks, user_id_clean)
                    
                    st.success(f"Ottimo {user_id_clean}! {len(chunks)} chunk indicizzati con successo.")
                    st.session_state.pdf_ready = True
                    st.session_state.current_user = user_id_clean
                except Exception as e:
                    st.error(f"Errore durante l'indicizzazione: {e}")
                    logger.error(f"Errore: {e}", exc_info=True)

# --- AREA CHAT ---
st.divider()

# Visualizzazione cronologia
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input utente
if prompt := st.chat_input("Fai una domanda sul documento..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        if not st.session_state.pdf_ready:
            full_response = "Per favore, carica e indicizza un PDF prima di iniziare la chat."
            response_placeholder.markdown(full_response)
        else:
            with st.spinner("Ricerca e generazione risposta in corso..."):
                try:
                    # Preparazione dello stato iniziale per il grafo
                    initial_state = {
                        "query": prompt,
                        "user_id": st.session_state.current_user,
                        "filename": uploaded_file.name,
                        "intent_data": {},
                        "context_chunks": [],
                        "final_answer": ""
                    }
                    
                    # Esecuzione del workflow LangGraph
                    # Usiamo invoke per ottenere il risultato finale dopo che tutti i nodi sono stati processati
                    result = rag_app.invoke(initial_state)
                    
                    full_response = result.get("final_answer", "Non sono riuscito a generare una risposta.")
                    response_placeholder.markdown(full_response)
                    
                except Exception as e:
                    full_response = f"Errore durante l'elaborazione della domanda: {e}"
                    response_placeholder.error(full_response)
                    logger.error(f"Errore Chat: {e}", exc_info=True)
        
        st.session_state.chat_history.append({"role": "assistant", "content": full_response})