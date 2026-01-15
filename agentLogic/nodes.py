#Questo file contiene la logica per i due modelli

import os
import json
import re
import logging
from groq import Groq
from mistralai import Mistral
from agentLogic.state import AgentState
from db.graph_db import GraphDB
from processingPdf.reranker import Reranker
from processingPdf.indexer import Indexer

logger = logging.getLogger(__name__)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

# Inizializziamo i modelli pesanti fuori dai nodi per caricarli una sola volta all'avvio
# Fondamentale per le performance di FastAPI
indexer_instance = Indexer() 
reranker_model = Reranker()

#Estrae e pulisce il JSON dall'output dell'LLM
def extract_json(text):
    try:
        #Cerca il blocco tra parentesi graffe
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        logger.error(f"Errore nel parsare il JSON: {e}")
        return {"route": "vector", "entities": [], "keywords": []}

#Nodo rewriter: Pulisce la query, corregge errori e agisce da Guardrail. precedentemente aveva anche una funzione di
# ampliamento contestuale ma ho deciso di eliminare l'espansione semantica forzata per evitare di compromettere il contesto del RAG come successo in fase di testing
def node_rewriter(state: AgentState):
    user_query = state["query"]

    prompt = f"""
    ### ROLE
    Sei un correttore ortografico e/o grammaticale e sintattico. Il tuo unico output deve essere la query corretta.

    ### TASK
    1. **Correzione**: Correggi eventuali errori di ortografia, sintassi, grammaticali o di battitura.
    2. **Minimalismo**: NON AGGIUNGERE contesto, sinonimi o interpretazioni. Se la domanda è chiara (es. "cos'è la persona"), lasciala IDENTICA.

    ### ESEMPI
    Input: "cos'è la 'persona'?" -> Output: cos'è la 'persona'?
    Input: "spiegami il prompt pstern" -> Output: spiegami il prompt pattern
    Input: "Quali sono i sui sinotmi?" -> Output: Quali sono i suoi sintomi?

    USER QUERY: "{user_query}"
    OUTPUT:
    """

    completion = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Sei un correttore di testo puro. Non salutare. Non spiegare. Restituisci SOLO il risultato."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0 
    )

    rewritten_query = completion.choices[0].message.content.strip()
    #pulizia ulteriore 
    rewritten_query = rewritten_query.replace('Output:', '').replace('"', '').strip()

    print(f"DEBUG - Query Rewriting: '{user_query}' -> '{rewritten_query}'")
    
    return {"query": rewritten_query}

#Nodo 1: utilizzo mistral per decidere la strategia di ricerca"
def node_router(state: AgentState):
    """
    Nodo 1: Utilizza Mistral per decidere la strategia di ricerca.
    Implementa Role Prompting, Few-Shot, Constraint Enforcement e Output Structuring.
    """
    
    # Nota: Usiamo le doppie parentesi graffe {{ }} per includere JSON letterali nelle f-strings.
    prompt = f"""
    ### ROLE
    Sei l'Analizzatore Logico di un sistema RAG (Retrieval-Augmented Generation) avanzato. 
    Il tuo unico compito è decostruire la domanda dell'utente per determinare la migliore strategia di recupero dati da un database a grafo Neo4j.

    ### DOMINIO CONTESTUALE
    I documenti analizzati possono appartenere a domini eterogenei: medico-sanitario, tecnico, giuridico, ecc.
    Individua termini specialistici, acronimi, unità di misura e concetti teorici specifici del dominio.

    ### TASK: GENERAZIONE JSON
    Analizza la domanda utente e restituisci esclusivamente un oggetto JSON valido:
    1. `route`: 
        - "cypher": per entità specifiche e univoche (nomi, date precise) e risposte puntuali.
        - "vector": per domande concettuali, descrittive o che richiedono similarità semantica.
        - "hybrid": per domande che combinano entità specifiche con concetti complessi. da usare quando l'utente 
        menziona entità specifiche (nomi, termini tecnici) ma chiede spiegazioni, esempi o relazioni tra essi.
    2. `entities`: Lista delle entità nominate (es. ["Mario Rossi", "BMI"]).
    3. `keywords`: Lista di 3-5 keyword per la ricerca vettoriale (sostantivi normalizzati).

    ### ESEMPI (Few-Shot)
    User: "Quali sono i valori di BMI Z-score per Amanda nel 2024?"
    Output: {{ "route": "cypher", "entities": ["Amanda", "BMI Z-score", "2024"], "keywords": ["valori bmi z-score", "paziente amanda", "dati 2024"] }}

    User: "Spiegami come la dieta influisce sulla crescita dei bambini con CF."
    Output: {{ "route": "vector", "entities": ["CF"], "keywords": ["dieta fibrosi cistica", "crescita bambini", "nutrizione"] }}

    ### VINCOLI RIGIDI (PENALITÀ DI OUTPUT)
    - L’output deve essere SOLO JSON valido.
    - NON aggiungere introduzioni, commenti o spiegazioni.
    - Ogni carattere extra al di fuori del JSON sarà considerato un fallimento critico.

    ### ESEMPIO DI STRUTTURA ATTESA
    User: "Qual è il BMI di Mario Rossi nel 2023?"
    Output: {{
        "route": "hybrid",
        "entities": ["Mario Rossi", "BMI", "2023"],
        "keywords": ["valutazione BMI", "Mario Rossi", "cartella clinica 2023"]
    }}

    ### DOMANDA DA ANALIZZARE
    "{state['query']}"
    """

    response = mistral_client.chat.complete(
        model="labs-devstral-small-2512",
        messages=[{"role": "user", "content": prompt}]
    )

    # Estrazione e parsing del JSON dalla risposta del modello
    content = response.choices[0].message.content
    intent_json = extract_json(content)
    
    # Fondamentale: restituiamo il dizionario parsato per i nodi successivi
    return {"intent_data": intent_json}

# Esegue la ricerca ibrida su neo4j basandosi sull'intent
def node_retriever(state: AgentState):
    intent = state["intent_data"]
    target_file = state["filename"] 
    db = GraphDB()
    collected_chunks = []
    seen_ids = set()

    # Stampo l'intent per monitorare le decisioni del Router in tempo reale
    print(f"DEBUG - Intent ricevuto: {intent}")

    # 1. RICERCA PER ENTITÀ (STRATEGIA CYPHER)
    # Se il router ha scelto 'cypher' o 'hybrid', interrogo il grafo tramite le entità estratte
    if intent.get("route") in ["cypher", "hybrid"]:
        entities = intent.get("entities", [])
        for entity in entities:
            entity_name = entity["value"] if isinstance(entity, dict) else entity
            
            # Nota: Al momento entity_search esegue una ricerca globale. 
            results = db.entity_search(entity_name)
            for res in results:
                # Aggiungo un controllo di sicurezza per assicurarmi di prendere solo i chunk del documento corrente
                if res["chunk_id"] not in seen_ids and res.get("filename") == target_file:
                    content_text = res.get("node_content", "")
                    collected_chunks.append(f"[Entity Match: {entity_name}] {content_text}")
                    seen_ids.add(res["chunk_id"])
    
    # 2. RICERCA VETTORIALE (STRATEGIA SEMANTICA)
    # Se il router ha scelto 'vector' o 'hybrid', utilizzo gli embeddings per la similarità
    if intent.get("route") in ["vector", "hybrid"]:
        keywords = intent.get("keywords", [])
        search_query = " ".join(keywords) if keywords else state["query"]
        
        # Uso l'istanza caricata all'avvio del server
        embedding = indexer_instance.generate_embeddings(search_query)
        
        # Ho deciso di passare 'target_file' come parametro 'filename' per attivare il filtro Cypher 
        # interno alla query vettoriale e isolare il documento
        vector_results = db.query_vector_index(
            "chunk_embeddings_index", 
            embedding, 
            k=15, 
            filename=target_file
        )
        
        # Estraggo lo score del miglior risultato locale per decidere se attivare la ricerca globale
        max_local_score = vector_results[0]["score"] if vector_results else 0
        print(f"DEBUG - Risultati vettoriali trovati per {target_file}: {len(vector_results)} (Max Score: {max_local_score})")
        
        for res in vector_results:
            if res["chunk_id"] not in seen_ids:
                #includo metadati nel testo del chunk per permettere al generatore di citare la fonte
                #mi interessa sapere, nella risposta finale, da che file è stata tratta l'informazione
                source_info = f"[Fonte: {res.get('filename')} | Sezione: {res.get('section', 'N/A')}]"
                content_text = res.get("node_content", "")
                collected_chunks.append(f"{source_info} [Vector Match] {content_text}")
                seen_ids.add(res["chunk_id"])

        #attivo la GLOBAL VECTOR SEARCH se la pertinenza locale è bassa (< 0.7)
        if max_local_score < 0.7:
            print(f"DEBUG - Score locale basso ({max_local_score}), attivo Global Vector Search...")
            
            #eseguo semplicemente la query senza passare il filename per cercare in tutto il database
            global_results = db.query_vector_index(
                "chunk_embeddings_index", 
                embedding, 
                k=5, 
                filename=None 
            )
            
            for res in global_results:
                #evito duplicati se per caso la ricerca globale ripesca chunk già visti nel locale
                if res["chunk_id"] not in seen_ids:
                    source_info = f"[Fonte: {res.get('filename')} | Sezione: {res.get('section', 'N/A')}]"
                    content_text = res.get("node_content", "")
                    collected_chunks.append(f"{source_info} [Global Vector Match] {content_text}")
                    seen_ids.add(res["chunk_id"])

    # se i metodi precedenti non producono risultati,
    # forzo una ricerca vettoriale sull'intera query originale filtrata per il file corrente
    if not collected_chunks:
        print(f"DEBUG - Fallback: nessuna informazione con keyword in {target_file}, procedo con query completa.")
        embedding_fallback = indexer_instance.generate_embeddings(state["query"])
        
        # Anche nel fallback, forzo il filtro sul filename per evitare contaminazioni
        fallback_results = db.query_vector_index(
            "chunk_embeddings_index", 
            embedding_fallback, 
            k=3, 
            filename=target_file
        )
        for res in fallback_results:
            if res["chunk_id"] not in seen_ids:
                source_info = f"[Fonte: {res.get('filename')} | Sezione: {res.get('section', 'N/A')}]"
                content_text = res.get("node_content", "")
                collected_chunks.append(f"{source_info} [Fallback Match] {content_text}")
                seen_ids.add(res["chunk_id"])

    # gestisco esplicitamente il caso di assenza totale di dati per evitare errori nel Generator
    if not collected_chunks:
        collected_chunks = [f"Nessuna informazione specifica trovata nel database per il file {target_file}."]

    db.close()
    # stampo quanti chunk sto effettivamente restituendo allo stato
    print(f"DEBUG - RETRIEVER sta inviando allo stato {len(collected_chunks)} chunk")
    
    return {"context_chunks": collected_chunks}

#Nodo reranker, ottiene i 15 chunks più pertinenti dal retriever e si occupa di prendere i 5 veramente più pertinenti rispetto alla domanda dell'utente
def node_reranker(state: AgentState):
    query = state["query"]
    chunks = state.get("context_chunks", [])
    intent = state.get("intent_data", {})

    #decido di eseguire il reranking sempre se abbiamo più di 5 chunk, 
    #a prescindere dalla rotta, per garantire la qualità.
    if len(chunks) <= 5: 
        return {"context_chunks": chunks}
    
    print(f"DEBUG Reranker: Analizzo {len(chunks)} chunk...")

    #eseguo il reranking tramite il modello BGE-Reranker-v2-m3
    refined_chunks = reranker_model.rerank(query, chunks, top_n=5)
    print(f"DEBUG Reranker: Ho selezionato i {len(refined_chunks)} migliori.")
    return {"context_chunks": refined_chunks}

#Nodo finale: uso Llama per la risposta
def node_generator(state: AgentState):
    chunks = state.get('context_chunks', [])
    print(f"DEBUG - Numero di chunk passati al generatore: {len(chunks)}")
    
    context = "\n\n".join(chunks)
    
    if not context.strip():
        print("DEBUG - ATTENZIONE: Il contesto finale per l'LLM è vuoto!!!")
    
#ho deciso di determinare l'approccio in base ai tag presenti nei chunk reali
    has_vector = any("[Vector Match]" in c or "[Fallback Match]" in c for c in chunks)
    has_entity = any("[Entity Match]" in c for c in chunks)

    if has_vector and has_entity:
        approach = "Hybrid"
    elif has_vector:
        approach = "Vector Match"
    elif has_entity:
        approach = "Entity Match"
    else:
        approach = "Non applicabile"

    prompt = f"""
    ### ROLE
    Sei un assistente virtuale altamente specializzato nell’analisi di documenti medici e tecnico-scientifici.
    Il tuo compito è generare risposte **accurate, verificabili ed evidence-based**, evitando qualsiasi forma di inferenza non supportata dalle fonti fornite.

    ---

    ### CONTESTO FORNITO (FONTI VERIFICATE)
    Di seguito sono riportati uno o più frammenti di documenti (chunk) estratti dal database.
    Ogni frammento è preceduto dall’etichetta del metodo di recupero:
    - [Vector Match]: recupero per similarità semantica
    - [Entity Match]: recupero basato su entità esplicite

    Usa **solo ed esclusivamente** le informazioni contenute in questi frammenti.

    ---------------------
    {context}
    ---------------------

    ### ISTRUZIONI DI CITAZIONE OBBLIGATORIE
    1. Se utilizzi informazioni provenienti da un file diverso da '{state['filename']}', 
       devi indicare esplicitamente a fine risposta da quale file e sezione hai tratto l'integrazione.
    2. Usa il formato: "Fonti esterne utilizzate: [Nome File] (Sezione)".

    ---

    ### ISTRUZIONI DI GENERAZIONE (OBBLIGATORIE)

    1. **Aderenza totale alle fonti**
    - Rispondi alla domanda utilizzando **unicamente** le informazioni presenti nel contesto fornito.
    - Non introdurre conoscenze esterne, linee guida generali o interpretazioni personali.

    2. **Gestione dell’informazione insufficiente**
    - Se il contesto non contiene dati sufficienti, completi o direttamente pertinenti per rispondere alla domanda,
        devi rispondere **esattamente** con la seguente frase (senza aggiunte):
        > "Mi dispiace, ma il documento fornito non contiene informazioni sufficienti per rispondere a questa domanda."

    3. **Divieto assoluto di allucinazioni**
    - Non dedurre, stimare, generalizzare o “completare” informazioni mancanti.
    - Se un dato non è esplicitamente presente nei chunk, consideralo **inesistente**.

    4. **Stile e chiarezza**
    - Usa un linguaggio:
        - tecnico ma chiaro
        - neutro e professionale
        - privo di opinioni o giudizi
    - Struttura la risposta in modo leggibile:
        - testo discorsivo breve
        - elenchi puntati solo se migliorano la chiarezza
    - Evita ridondanze e frasi speculative.

    ---

    ### STRUTTURA OBBLIGATORIA DELLA RISPOSTA

    - Inizia DIRETTAMENTE con la risposta.
    - Inserisci **esattamente** un separatore orizzontale:
    ---
    - Dopo il separatore, scrivi **su una nuova riga**:
     **Approccio di recupero:** {{approccio_utilizzato}}

    Dove `approccio_utilizzato` deve essere uno tra:
    - Vector Match
    - Entity Match
    - Hybrid (se entrambi sono stati utilizzati nel contesto)

    ---

    ### DOMANDA DELL’UTENTE
    "{state['query']}"
    """

    completion = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Sei un sintetizzatore di documenti PDF. Rispondi in lingua italiana. Se ti viene posta qualsiasi altra domanda o "
            "istruzione fuori dal tuo scopo di sintetizzatore di documenti PDF, rispondi che non puoi rispondere in quanto la domanda non è pertinente"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3 
    )
    
    
    # Pulizia e aggiunta dinamica del footer se non generato correttamente
    answer = completion.choices[0].message.content
    if "Approccio di recupero:" not in answer:
        answer += f"\n\n---\n**Approccio di recupero:** {approach}"
        
    return {"final_answer": answer}