# GraphRAG Chatbot
<img width="1024" height="1024" alt="logo piccolo" src="https://github.com/user-attachments/assets/e5cd1867-b25c-4c45-83e2-ba4106efe221" />

<div align="center">
  <img width="300" alt="logo piccolo" src="https://github.com/user-attachments/assets/e5cd1867-b25c-4c45-83e2-ba4106efe221" />
  <br>
  <em>Un sistema di recupero deterministico potenziato da Knowledge Graph e Orchestratori LLM.</em>
</div>

---

## 📋 Introduzione

**GraphRAG Chatbot** è un sistema avanzato di *Retrieval-Augmented Generation* (RAG) progettato per analizzare documenti PDF complessi con un approccio **deterministico**.

A differenza dei sistemi RAG tradizionali che si affidano esclusivamente alla similarità vettoriale, questo progetto combina la potenza dei **Database a Grafo (Neo4j)** con l'orchestrazione semantica di **LangGraph**. L'obiettivo è eliminare le "allucinazioni" dell'AI: il modello non genera risposte basandosi sulla sua memoria di addestramento, ma agisce come un sintetizzatore rigoroso di informazioni estratte e validate dal documento caricato.

Il sistema è progettato per la privacy: può funzionare interamente **offline** scaricando i modelli in locale, creando una base di conoscenza privata che si espande ad ogni nuovo documento caricato.

---

## 🏗️ Architettura del Sistema

Il cuore del sistema è un'architettura a stati finiti (DAG - Directed Acyclic Graph) che coordina l'ingestione, l'analisi e il recupero delle informazioni in modo molto più rapido e prevedibile rispetto ai classici agenti "ReAct".

![Architettura GraphRAG] <img width="954" height="798" alt="Immagine 2026-01-19 145438" src="https://github.com/user-attachments/assets/d47364e5-419a-4604-929e-565e9cfd0199" />

### 1. Ingestion & Elaborazione del Testo
La fase di ingestione non si limita a "leggere" il testo, ma ne comprende la struttura.
* **Parsing:** Utilizziamo [spaCyLayout](https://spacy.io/) per estrarre testo, tabelle e layout, mantenendo la gerarchia logica del documento.
* **Chunking:** Il testo viene suddiviso in frammenti (chunk) con una strategia ricorsiva per preservare il contesto semantico tra paragrafi adiacenti.

### 2. Knowledge Graph & Embedding
I dati non finiscono in un semplice archivio vettoriale, ma in un **Knowledge Graph**.
* **Database:** Utilizziamo [Neo4j AuraDB](https://neo4j.com/cloud/aura/), un database a grafo nativo che ci permette di collegare i chunk non solo per vicinanza matematica, ma per relazioni logiche ed entità condivise.
* **Embedding Model:** [intfloat/multilingual-e5-large](https://huggingface.co/intfloat/multilingual-e5-large). Scelto per le sue eccellenti prestazioni multilingua e la profondità a 1024 dimensioni, cattura sfumature semantiche complesse.
* **Named Entity Recognition (NER):** [GLiNER (urchade/gliner_medium-v2.1)](https://huggingface.co/urchade/gliner_medium-v2.1). 
    * *Perché non spaCy?* In fase di test, modelli classici fallivano su termini scientifici (es. classificando "bmi-z score" come persona).
    * *La soluzione:* GLiNER è un modello *zero-shot* capace di identificare entità eterogenee (nomi, luoghi, concetti tecnici, riferimenti normativi) senza training specifico. Queste entità diventano nodi nel grafo, creando "ponti" semantici tra concetti distanti nel testo.

![Neo4j Graph]
<img width="1395" height="858" alt="Immagine 2026-01-19 150409" src="https://github.com/user-attachments/assets/1b622597-6b75-41ce-8010-c54230807365" />

---

## 🧠 Orchestrazione con LangGraph

Il flusso logico è gestito da [LangGraph](https://langchain-ai.github.io/langgraph/), che permette di creare cicli decisionali intelligenti.

### Query Rewriting
Prima di processare la domanda dell'utente, un nodo dedicato si occupa di **riscrivere la query**. Questo corregge errori grammaticali, ortografici o di distrazione, ottimizzando l'input per il motore di ricerca ed evitando che prompt scritti male compromettano il recupero.

### Router Strategico (Mistral)
Come "cervello" decisionale utilizziamo [Mistral AI](https://mistral.ai/), in particolare labs-devstral-small-2512.
* **Perché Mistral?** È un modello leggero, veloce ed estremamente capace nel reasoning logico e nella produzione di JSON strutturati.
* **Cosa fa:** Non risponde alla domanda, ma *decide come* rispondere. Analizza l'intento dell'utente e sceglie la strategia di recupero migliore.

---

## 🔍 Strategie di Recupero

Il sistema adotta un approccio adattivo al recupero delle informazioni:

![Strategie di Recupero]
<img width="933" height="643" alt="Immagine 2026-01-19 145453" src="https://github.com/user-attachments/assets/892e816d-e443-4cfa-9187-258d822175fe" />

1.  **Vector Match:** Attivata per domande concettuali o descrittive. Cerca i chunk semanticamente più vicini nello spazio vettoriale.
2.  **Cypher Query (Entity Based):** Se GLiNER rileva entità specifiche nella domanda (es. "Svezia"), Mistral estrae i parametri e una funzione Python costruisce una query Cypher sicura per interrogare Neo4j. Questo garantisce precisione chirurgica, ma soprattutto una velocità estrema dato che una query su db è estremamente più veloce che una ricerca vettoriale.
3.  **Hybrid Search:** Combina i risultati vettoriali con quelli basati sulle entità per massimizzare il contesto.
4.  **Global Search:** Se lo score di pertinenza dei risultati locali sul documento attivo è basso (es. < 0.7), il sistema estende automaticamente la ricerca all'intera base di conoscenza (tutti i PDF caricati in precedenza), garantendo una risposta anche se l'informazione è dispersa.

### Reranking (Il Filtro di Qualità)
Spesso la ricerca vettoriale recupera chunk simili ma non rilevanti. Per questo, implementiamo una fase di **Reranking**.
* **Modello:** [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3).
* **Funzionamento:** Questo modello (Cross-Encoder) riceve in input i top ~15 chunk grezzi dal retriever e la domanda utente. Analizza la coppia parola per parola e riordina i risultati.
* **Output:** Solo i chunk con alta pertinenza vengono passati alla sintesi, eliminando il rumore.

---

## 📝 Sintesi Finale

L'ultimo passaggio è affidato a un LLM generativo (**llama-3.1-8b-instant** via [Groq](https://groq.com/)).
È fondamentale notare che questo modello **non genera conoscenza**. Agisce puramente come un **sintetizzatore**: prende i chunk validati dal Reranker e confeziona una risposta naturale e coerente, rigorosamente ancorata alle fonti fornite.

---

## 💻 Interfaccia Utente

Il frontend è sviluppato in **React**.

### Home 
![Home Screen]
<img width="1897" height="904" alt="Immagine 2026-01-19 145123" src="https://github.com/user-attachments/assets/d0ba9cc5-2f18-4cbb-baeb-d2f843e7394f" />

### Chat 
Visualizzazione chiara della risposta, con indicazione delle fonti e della strategia di recupero utilizzata.
![Chat]
<img width="781" height="509" alt="Immagine 2026-01-19 145946" src="https://github.com/user-attachments/assets/bc0e0784-4eb7-49fa-9a87-d691ee392437" />

---

## 🛠️ Tech Stack

* **Frontend:** React, TypeScript, Vite, TailwindCSS.
* **Backend:** FastAPI, Uvicorn.
* **AI Orchestration:** LangGraph, LangChain.
* **Database:** Neo4j AuraDB.
* **Models:**
    * *Embedding:* Multilingual-E5-Large
    * *NER:* GLiNER Medium v2.1
    * *Reranking:* BGE-Reranker v2-m3
    * *LLM:* Mistral (Routing), Llama 3.1 (Synthesis)
* **Hosting:** Hugging Face Spaces (Docker).

---

## 👨‍💻 Crediti

Questo progetto è nato come evoluzione di un'idea concepita durante il mio tirocinio curriculare presso l'azienda **Logogramma**.

Sviluppato da **Valerio Botto**.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/valerio-botto-4844b2190/)
