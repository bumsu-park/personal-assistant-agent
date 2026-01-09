import logging 
import time
import uuid
from typing import List, Dict, Optional
from src.config import Config 


logger = logging.getLogger(__name__)

try:
    from langchain_openai import OpenAIEmbeddings
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    RAG_AVAILABLE = True
except ImportError:
    logger.warning("RAG dependencies not installed")
    RAG_AVAILABLE = False
    

class RAGService: 
    
    def __init__(self):
        logger.info("Initializing RAG Service")
        
        self.client = QdrantClient(path=Config.VECTOR_STORE_DIR)
        self.collection_name = "documents"
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=Config.OPENAI_API_KEY
        )
        
        try: 
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' already exists")
        except Exception as e:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=1536,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created collection '{self.collection_name}'")
        
        logger.info("RAG Service initialized successfully")
        
    def add_documents(
        self, 
        texts: List[str],
        metadatas: List[Dict],
        user_id: str
    ): 
        logger.info(f"Adding {len(texts)} documents for user {user_id}")
        
        embeddings = self.embeddings.embed_documents(texts)
        timestamp = int(time.time() * 1000) 
        
        points = []
        
        for i, (text, embedding, metadata) in enumerate(zip(texts, embeddings, metadatas)):
            metadata["user_id"] = user_id
            metadata["text"] = text
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=metadata
            )
            points.append(point)
            
        self.client.upsert(
            collection_name=self.collection_name,
            points=points   
        )
                
        logger.info(f"Successfully added {len(texts)} documents for user {user_id}")
        
    def search_document(
        self, 
        query: str, 
        user_id: str, 
        k: int = 5
    ) -> List[Dict]: 
        logger.info(f"Searching for top {k} documents for user {user_id}")
        query_embedding = self.embeddings.embed_query(query)
        
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding, 
            limit=k,
            with_payload=True,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )
        ).points
        
        documents = []
        for result in results:
            documents.append({
                "content": result.payload.get("text", ""),
                "metadata": result.payload,
                "score": result.score
            })
            
        logger.info(f"Found {len(documents)} documents for user {user_id}")
        return documents
    

_rag_service = None

def get_rag_service() -> Optional[RAGService]:
    if not RAG_AVAILABLE:
        return None
    
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
