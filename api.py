from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agentLogic.graph import app as rag_app
from processingPdf.indexer import Indexer
import shutil
import os
import logging

port = int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Middleware CORS per il frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inizializzazione dell'Indexer 
indexer_worker = Indexer()

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...), user_id: str = Form(...)):
    """
    Endpoint per caricare un PDF e indicizzarlo in Neo4j.
    """
    # Cartella temporanea per processare il file
    upload_dir = "temp_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        # 1. Salva il file fisicamente sul server
        logger.info(f"Ricezione file: {file.filename} per l'utente: {user_id}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Avvia la pipeline di indicizzazione (Extractor -> Chunker -> Neo4j)
        indexer_worker.index_pdf(file_path, user_id)
        
        return {
            "status": "success",
            "message": "Indicizzazione completata con successo", 
            "filename": file.filename
        }

    except Exception as e:
        logger.error(f"Errore durante l'upload/indicizzazione: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # 3. Pulizia file temporaneo
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/chat")
async def chat(query: str, filename: str, user_id: str):
    """
    Endpoint per interrogare il sistema GraphRAG tramite LangGraph.
    """
    try:
        # Stato iniziale per il grafo
        initial_state = {
            "query": query,
            "user_id": user_id,
            "filename": filename,
            "intent_data": {},
            "context_chunks": [],
            "final_answer": ""
        }
        
        # Esecuzione del workflow
        result = rag_app.invoke(initial_state)
        
        return {"answer": result["final_answer"]}
    
    except Exception as e:
        logger.error(f"Errore nella chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore durante l'elaborazione della domanda.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)