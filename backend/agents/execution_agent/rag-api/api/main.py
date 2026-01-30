"""
FastAPI endpoint for RAG retrieval service
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
import logging
    
from chromadb import Client
from chromadb.config import Settings
from fastapi import HTTPException
import chromadb

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="RAG Retrieval API",
    description="Vector similarity search for code documentation",
    version="1.0.0"
)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

from pydantic import BaseModel, ConfigDict

class RetrievalRequest(BaseModel):
    query: str
    library_name: str = "pyautogui"
    top_k: int = 5
    similarity_threshold: float = 0.3

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "how to click a button",
                "library_name": "pyautogui",
                "top_k": 5,
                "similarity_threshold": 0.3
            }
        }
    )


class Context(BaseModel):
    """Single context result"""
    rank: int
    content: str
    similarity: float
    metadata: Dict

class RetrievalResponse(BaseModel):
    """Response model for retrieval endpoint"""
    query: str
    library_name: str
    contexts: List[Context]
    total_found: int
    processing_time_ms: float

# ============================================================================
# RAG SERVICE CLASS
# ============================================================================

class RAGRetrievalService:
    """Service for vector similarity retrieval"""
    
    def __init__(self):
        self.clients = {}  # Cache for different libraries
        self.models = {}   # Cache for embedding models
        
        # Paths (inside Docker container)
        self.vectordb_base = Path("/app/data/vectordb")
        self.models_base = Path("/app/data/models")
        
        logger.info("RAG Retrieval Service initialized")


    def _get_client(self, library_name: str):
        if library_name not in self.clients:
            vectordb_path = self.vectordb_base / library_name

            if not vectordb_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Vector database for '{library_name}' not found at {vectordb_path}"
                )

            logger.info(f"Connecting to {library_name} vector database at {vectordb_path}...")

            try:
                client = chromadb.PersistentClient(path=str(vectordb_path))
                
                # ✅ List collections first to debug
                collections = client.list_collections()
                logger.info(f"Available collections: {[c.name for c in collections]}")
                
                collection_name = f"{library_name}_embeddings"
                
                # ✅ Use list_collections() result instead of get_collection()
                collection = None
                for c in collections:
                    if c.name == collection_name:
                        collection = c
                        break
                
                if collection is None:
                    raise ValueError(
                        f"Collection '{collection_name}' not found. "
                        f"Available: {[c.name for c in collections]}"
                    )
                
                self.clients[library_name] = {
                    "client": client,
                    "collection": collection
                }
                
                logger.info(f"✅ Connected to {collection_name} ({collection.count()} docs)")
                
            except Exception as e:
                logger.error(f"ChromaDB connection failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load collection: {str(e)}"
                )

        return self.clients[library_name]


    
    def _get_model(self, library_name: str):
        """Get or load embedding model for library"""
        if library_name not in self.models:
            model_path = self.models_base / library_name / "embedding_model"
            
            if not model_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Embedding model for '{library_name}' not found"
                )
            
            logger.info(f"Loading {library_name} embedding model...")
            self.models[library_name] = SentenceTransformer(str(model_path))
            logger.info(f"✅ Model loaded")
        
        return self.models[library_name]
    
    def retrieve(self, query: str, library_name: str, 
                top_k: int, similarity_threshold: float) -> List[Dict]:
        """Retrieve relevant contexts for query"""
        import time
        start = time.time()
        
        # Get client and model
        db = self._get_client(library_name)
        model = self._get_model(library_name)
        
        # Generate query embedding
        query_embedding = model.encode([query])[0]
        
        # Search
        results = db['collection'].query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k * 2  # Get extra for filtering
        )
        
        # Format results
        contexts = []
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            similarity = 1 - distance
            
            if similarity >= similarity_threshold:
                contexts.append({
                    'rank': len(contexts) + 1,
                    'content': doc,
                    'similarity': similarity,
                    'metadata': metadata
                })
            
            if len(contexts) >= top_k:
                break
        
        processing_time = (time.time() - start) * 1000
        
        logger.info(f"Retrieved {len(contexts)} contexts in {processing_time:.2f}ms")
        
        return contexts, processing_time

# Initialize service
rag_service = RAGRetrievalService()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "RAG Retrieval API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "loaded_libraries": list(rag_service.clients.keys()),
        "loaded_models": list(rag_service.models.keys())
    }

@app.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_contexts(request: RetrievalRequest):
    """
    Retrieve relevant contexts for a query
    
    Example:
    ```
    POST /retrieve
    {
        "query": "how to click a button",
        "library_name": "pyautogui",
        "top_k": 5,
        "similarity_threshold": 0.3
    }
    ```
    """
    try:
        contexts, processing_time = rag_service.retrieve(
            query=request.query,
            library_name=request.library_name,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        return RetrievalResponse(
            query=request.query,
            library_name=request.library_name,
            contexts=contexts,
            total_found=len(contexts),
            processing_time_ms=processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=str(e))