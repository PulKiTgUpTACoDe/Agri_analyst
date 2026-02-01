"""Vector store management for Agri Analyst using Pinecone.

This module provides vector store initialization and management for
semantic search over agricultural documents and data.

Uses local embeddings (sentence-transformers) to generate 1024-dim vectors
matching your Pinecone index configuration.
"""
import os
from typing import Optional, List
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer


class VectorStoreManager:
    """Manages Pinecone vector store for agricultural knowledge base.
    
    Uses local sentence-transformers model to generate embeddings
    that match your Pinecone index (1024 dimensions).
    """
    
    def __init__(self):
        """Initialize vector store manager."""
        self.pc: Optional[Pinecone] = None
        self.index = None
        self.embedding_model = None
        self._initialized = False
    
    def initialize(self):
        """Initialize Pinecone and embedding model.
        
        Returns:
            Pinecone Index instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        if self._initialized:
            return self.index
        
        # Get configuration from environment
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "agri-analyst")
        
        if not api_key:
            raise ValueError(
                "PINECONE_API_KEY environment variable not set. "
                "Please add it to your .env file or Vercel environment variables."
            )
        
        # Initialize Pinecone client
        print(f"[VECTOR_STORE] Connecting to Pinecone...")
        self.pc = Pinecone(api_key=api_key)
        
        # Connect to existing index
        print(f"[VECTOR_STORE] Connecting to index: {index_name}")
        self.index = self.pc.Index(index_name)
        
        print(f"[VECTOR_STORE] Loading local embedding model...")
        self.embedding_model = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B')
        
        self._initialized = True
        print("[VECTOR_STORE] Initialization complete")
        print(f"[VECTOR_STORE] Using local embeddings: {self.embedding_model.get_sentence_embedding_dimension()} dims")
        return self.index
    
    def add_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None):
        """Add documents to the vector store.
        
        Embeds text locally using sentence-transformers.
        
        Args:
            texts: List of text documents to add
            metadatas: Optional list of metadata dicts for each document
        """
        if not self._initialized:
            self.initialize()
        
        # Generate embeddings locally
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        
        # Prepare vectors for Pinecone
        vectors = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            vector_id = f"doc_{abs(hash(text))}"
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            metadata["text"] = text  # Store original text
            
            vectors.append({
                "id": vector_id,
                "values": embedding.tolist(),  # Manual embedding values
                "metadata": metadata
            })
        
        # Upsert to Pinecone
        try:
            self.index.upsert(vectors=vectors)
            print(f"[VECTOR_STORE] ✓ Stored {len(texts)} documents (embedded locally)")
        except Exception as e:
            print(f"[VECTOR_STORE] ✗ Storage failed: {e}")
            raise
    
    def similarity_search(self, query: str, k: int = 5) -> List[dict]:
        """Search for similar documents.
        
        Embeds query locally using sentence-transformers.
        
        Args:
            query: Search query text
            k: Number of results to return
            
        Returns:
            List of matching documents with metadata
        """
        if not self._initialized:
            self.initialize()
        
        # Generate query embedding locally
        query_embedding = self.embedding_model.encode([query], show_progress_bar=False)[0]
        
        # Query Pinecone with manual embedding
        try:
            results = self.index.query(
                vector=query_embedding.tolist(),
                top_k=k,
                include_metadata=True
            )
        except Exception as e:
            print(f"[VECTOR_STORE] Query error: {e}")
            return []
        
        # Convert to expected format
        documents = []
        for match in results.get('matches', []):
            metadata = match.get('metadata', {})
            documents.append({
                "content": metadata.get("text", ""),
                "metadata": metadata,
                "score": match.get('score', 0.0)
            })
        
        return documents


# Singleton instance
_vector_store_manager: Optional[VectorStoreManager] = None


def get_vector_store():
    """Get or create the global vector store instance.
    
    Returns:
        VectorStoreManager: Initialized vector store
    """
    global _vector_store_manager
    
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
    
    return _vector_store_manager.initialize()


def add_texts(texts: List[str], metadatas: Optional[List[dict]] = None):
    """Add texts to vector store.
    
    Args:
        texts: List of text documents
        metadatas: Optional metadata for each document
    """
    global _vector_store_manager
    
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
        _vector_store_manager.initialize()
    
    _vector_store_manager.add_documents(texts, metadatas)


def similarity_search(query: str, k: int = 5) -> List[dict]:
    """Search for similar documents.
    
    Args:
        query: Search query
        k: Number of results to return
        
    Returns:
        List of matching documents
    """
    global _vector_store_manager
    
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
        _vector_store_manager.initialize()
    
    return _vector_store_manager.similarity_search(query, k)
