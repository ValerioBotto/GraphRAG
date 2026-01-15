#Questo file gestisce la connessione e tutte le query Cypher

from neo4j import GraphDatabase, exceptions
import logging
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

#Classe per la gestione della connessione e delle operazioni di base con Neo4j
class GraphDB:
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, database: Optional[str] = None):

        #Carica credenziali dalle varibiali dambiente o usa i default del progetto
        self.uri = uri or os.getenv("NEO4J_URI")
        self.user = user or os.getenv("NEO4J_USERNAME")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE")

        # VALIDAZIONE: Forza la presenza di tutte le variabili
        if not all([self.uri, self.user, self.password, self.database]):
            missing_vars = [name for name, val in [
                ("NEO4J_URI", self.uri), 
                ("NEO4J_USERNAME", self.user), 
                ("NEO4J_PASSWORD", self.password), 
                ("NEO4J_DATABASE", self.database)
            ] if not val]
            
            # Rilancia un errore chiaro se le credenziali non sono definite nell'ambiente
            raise ValueError(
                f"Credenziali Neo4j mancanti. Assicurati che le seguenti variabili siano definite nel file .env e caricate correttamente: {', '.join(missing_vars)}"
            )
        
        self.driver = None

        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()

            self.create_indexes_and_constraints()
            logger.info(f"Connessione a Neo4j (DB: {self.database}) stabilita con successo.")
        except Exception as e:
            logger.error(f"Errore durante la connessione a Neo4j su {self.uri}: {e}")
            raise
    
    #Chiude la connessione al driver Neo4j
    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Connessione a Neo4j chiusa.")
    
    #Crea indici e vincoli essenziali per le performance del RAG
    def create_indexes_and_constraints(self):
        index_queries = [
            #Vincoli per l'unicità dei nodi principali (Documenti, Utenti)
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.filename IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            #Indice per la ricerca di Chunk tramite ID (utile per la citazione del chunk)
            "CREATE INDEX IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)",
        ]

        with self.driver.session(database=self.database) as session:
            for query in index_queries:
                try:
                    session.run(query)
                except exceptions.ClientError as e:
                    #Logga l'errore, ma ignora quelli noti di indice/vincolo già esistente
                    if "IndexAlreadyExists" not in e.message and "ConstraintAlreadyExists" not in e.message:
                        logger.error(f"Errore nell'esecuzione della query indice '{query}': {e}")
                        raise
                except Exception as e:
                    logger.error(f"Errore inatteso nell'esecuzione della query indice '{query}': {e}")
                    raise
        
        logger.info("Indici e vincoli Neo4j verificati/creati.")

    
    # --- Operazioni Crud per il RAG ---
    #Crea o Aggiorna un nodo Document
    def create_document_node(self, filename: str, title: str = None):
        query = """
        MERGE (d:Document {filename: $filename})
        ON CREATE SET
            d.created_at = datetime(),
            d.title = COALESCE($title, $filename)
        ON MATCH SET d.last_updated = datetime()
        RETURN d
        """
        return self.run_query(query, {"filename": filename, "title": title})
    
    #Crea o aggiorna un nodo User e registra l'attività
    def create_user_node(self, user_id: str):
        query = """
        MERGE (u:User {id: $user_id})
        ON CREATE SET u.created_at = datetime(), u.last_activity = datetime()
        ON MATCH SET u.last_activity = datetime()
        RETURN u
        """
        return self.run_query(query, {"user_id": user_id})
    
    #Crea una relazione ACCESSED tra User e Document
    def link_user_to_document(self, user_id: str, filename: str):
        query = """
        MATCH (u:User {id: $user_id})
        MATCH (d:Document {filename: $filename})
        MERGE (u)-[r:ACCESSED]->(d)
        ON CREATE SET r.first_access = datetime(), r.last_access = datetime()
        ON MATCH SET r.last_access = datetime()
        RETURN u, d, r
        """
        return self.run_query(query, {"user_id": user_id, "filename": filename})
    
    #Aggiunge un nodo Chunk collegato al nodo Document
    def add_chunk_to_document(self, filename: str, chunk_id: str, content: str, embedding: List[float], metadata: Dict[str, Any]):
        query = """
        MATCH (d:Document {filename: $filename})
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.content = $content,
            c.embedding = $embedding,
            c.section = $section,
            c.source = $filename,
            c.last_updated = datetime()
        MERGE (d)-[:HAS_CHUNK]->(c)
        RETURN c
        """
        parameters = {
            "filename": filename,
            "chunk_id": chunk_id,
            "content": content,
            "embedding": embedding,
            "section": metadata.get("section", "unspecified")
        }
        return self.run_query(query, parameters)
    
    #Crea un indice vettoriale per la ricerca di similarità
    def create_vector_index(self, index_name: str, node_label: str, property_name: str, vector_dimensions: int):        
        query = f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS 
        FOR (n:{node_label})
        ON (n.{property_name})
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {vector_dimensions},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        try:
            self.run_query(query)
            logger.info(f"Indice vettoriale '{index_name}' creato con successo per {node_label}.")
        except Exception as e:
            logger.error(f"Errore nella creazione dell'indice vettoriale '{index_name}': {e}")
            raise

        #Esegue una ricerca vettoriale, opzionalemnte filtrata per documento
    def query_vector_index(self, index_name: str, query_embedding: List[float], k: int = 5, filename: Optional[str] = None) -> List[Dict[str, Any]]:

        # db.index.vector.queryNodes è la procedura Cypher per la ricerca vettoriale
        if filename:
            # Ricerca filtrata per documento specifico (più precisa)
            query = f"""
            CALL db.index.vector.queryNodes('{index_name}', $k, $query_embedding)
            YIELD node, score
            WITH node, score
            MATCH (d:Document {{filename: $filename}})-[:HAS_CHUNK]->(node)
            RETURN node.content AS node_content, score, node.chunk_id AS chunk_id, node.section AS section, d.filename AS filename
            """
            parameters = {"query_embedding": query_embedding, "filename": filename, "k": k}
        else:
            # Ricerca globale su tutti i documenti (usato per cross-document search)
            query = f"""
            CALL db.index.vector.queryNodes('{index_name}', $k, $query_embedding)
            YIELD node, score
            RETURN node.content AS node_content, score, node.chunk_id AS chunk_id, node.section AS section, node.source AS filename
            """
            parameters = {"query_embedding": query_embedding, "k": k}
        
        results = []
        try:
            records = self.run_query(query, parameters)
            for record in records:
                results.append({
                    "node_content": record["node_content"],
                    "score": record["score"],
                    "chunk_id": record["chunk_id"],
                    "section": record.get("section", "N/A"), # Usiamo .get per sicurezza
                    "filename": record.get("filename", "Unknown"),
                })
            logger.debug(f"Ricerca vettoriale ha trovato {len(results)} risultati.")
            return results
        except Exception as e:
            logger.error(f"Errore durante la query dell'indice vettoriale: {e}")
            return []
    
    def add_entity_to_chunk(self, entity_name, entity_type, chunk_id):
        query = """
        MERGE (e:Entity {name: $name, type: $type})
        WITH e
        MATCH (c:Chunk {chunk_id: $chunk_id})
        MERGE (c)-[:CONTAINS_ENTITY]->(e)
        """
        params = {"name": entity_name, "type": entity_type, "chunk_id": chunk_id}
        self.run_query(query, params)

    #Esegue una ricerca esatta basata sui nodi Entity
    def entity_search(self, entity_name: str) -> List[Dict[str, Any]]:
        query = """
        MATCH (e:Entity)
        WHERE toLower(e.name) = toLower($name)
        MATCH (e)<-[:CONTAINS_ENTITY]-(c:Chunk)
        RETURN c.content AS node_content, c.chunk_id AS chunk_id, 1.0 AS score, c.section AS section, c.source AS filename
        LIMIT 5
        """
        results = []
        try:
            records = self.run_query(query, {"name": entity_name})
            for record in records:
                results.append({
                    "node_content": record.get("node_content"),
                    "chunk_id": record.get("chunk_id"),
                    "score": record.get("score"),
                    "section": record.get("section"),
                    "filename": record.get("filename")
                })
            return results
        except Exception as e:
            logger.error(f"Errore nella ricerca per entità '{entity_name}': {e}")
            return []
    
    def run_query(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        if not self.driver:
            raise RuntimeError("Driver Neo4j non inizializzato.")

        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters)
            return result.data()