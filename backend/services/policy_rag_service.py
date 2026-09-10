import os
import json
import uuid
import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports for ML/Vector libraries to avoid startup crashes if missing
try:
    import faiss
except ImportError:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None

from services.metadata_service import metadata_service

from utils.path_resolver import resolve_user_data_resource, resolve_bundled_resource, get_user_data_dir

# Configuration constants
policy_storage_env = os.getenv("HADIL_POLICY_STORAGE_DIR")
if policy_storage_env:
    STORAGE_BASE_DIR = os.path.abspath(policy_storage_env)
else:
    STORAGE_BASE_DIR = resolve_user_data_resource("storage/policies")

ORIGINAL_DIR = os.path.join(STORAGE_BASE_DIR, "original")
INDEX_DIR = os.path.join(STORAGE_BASE_DIR, "index")
FAISS_INDEX_PATH = os.path.join(INDEX_DIR, "faiss_index.bin")
CHUNK_METADATA_PATH = os.path.join(INDEX_DIR, "chunk_metadata.json")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("HADIL_POLICY_THRESHOLD", "0.65"))


def _ensure_embedding_cache_env() -> str:
    """
    Cloud/Render: download weights into a writable cache. Windows: unused when
    the bundled models/all-MiniLM-L6-v2 directory is present.
    """
    cache_dir = os.getenv("HADIL_EMBEDDING_CACHE_DIR")
    if not cache_dir:
        cache_dir = os.path.join(get_user_data_dir(), "models", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    os.environ.setdefault("HF_HOME", cache_dir)
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", cache_dir)
    os.environ.setdefault("TRANSFORMERS_CACHE", cache_dir)
    return cache_dir


def resolve_embedding_model_source() -> dict:
    """
    Resolve MiniLM without committing model weights.

    Priority:
    1. HADIL_EMBEDDING_MODEL_PATH (explicit directory)
    2. Bundled Windows/offline path models/all-MiniLM-L6-v2
    3. Cached copy under HADIL_DATA_DIR/models/all-MiniLM-L6-v2
    4. Hugging Face hub id (downloaded/cached at first use)
    """
    explicit = (os.getenv("HADIL_EMBEDDING_MODEL_PATH") or "").strip()
    if explicit and os.path.exists(explicit):
        return {"source": "explicit_path", "location": explicit, "hub_download": False}

    bundled = resolve_bundled_resource(os.path.join("models", EMBEDDING_MODEL_NAME))
    if os.path.exists(bundled):
        return {"source": "bundled", "location": bundled, "hub_download": False}

    cached_local = os.path.join(get_user_data_dir(), "models", EMBEDDING_MODEL_NAME)
    if os.path.exists(cached_local):
        return {"source": "local_cache", "location": cached_local, "hub_download": False}

    cache_dir = _ensure_embedding_cache_env()
    return {
        "source": "huggingface_hub",
        "location": EMBEDDING_MODEL_NAME,
        "cache_dir": cache_dir,
        "hub_download": True,
    }


class PolicyRAGService:
    def __init__(self):
        self.model = None
        self.index = None
        self.chunks_metadata: List[Dict[str, Any]] = [] # Each item: {id, doc_id, filename, scope, chunk_index, text, embedding}
        self.is_initialized = False
        self.threshold = DEFAULT_SIMILARITY_THRESHOLD

    def _ensure_directories(self):
        os.makedirs(ORIGINAL_DIR, exist_ok=True)
        os.makedirs(INDEX_DIR, exist_ok=True)

    def _get_model(self):
        if self.model is None:
            if SentenceTransformer is None:
                raise RuntimeError(
                    "sentence-transformers is not installed; Policy RAG cannot load MiniLM."
                )
            resolved = resolve_embedding_model_source()
            location = resolved["location"]
            logger.info(
                f"[POLICY RAG] Loading SentenceTransformer from {resolved['source']}: {location}"
            )
            try:
                self.model = SentenceTransformer(location)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load embedding model '{EMBEDDING_MODEL_NAME}' "
                    f"(source={resolved['source']}). RAG is required and was not disabled. {exc}"
                ) from exc
        return self.model


    def initialize(self):
        """
        Loads index and metadata from disk on startup. Survive restart.
        """
        self._ensure_directories()
        
        # Initialize FAISS index
        if faiss is not None:
            if os.path.exists(FAISS_INDEX_PATH):
                try:
                    logger.info(f"[POLICY RAG] Loading FAISS index from {FAISS_INDEX_PATH}")
                    self.index = faiss.read_index(FAISS_INDEX_PATH)
                except Exception as e:
                    logger.error(f"[POLICY RAG] Failed to load FAISS index: {e}")
                    self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
            else:
                self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        
        # Load chunk metadata
        if os.path.exists(CHUNK_METADATA_PATH):
            try:
                with open(CHUNK_METADATA_PATH, "r", encoding="utf-8") as f:
                    self.chunks_metadata = json.load(f)
                logger.info(f"[POLICY RAG] Loaded {len(self.chunks_metadata)} chunk metadata records.")
            except Exception as e:
                logger.error(f"[POLICY RAG] Failed to load chunk metadata JSON: {e}")
                self.chunks_metadata = []

        self.is_initialized = True
        logger.info("[POLICY RAG] Initialization complete.")

    def set_threshold(self, value: float):
        self.threshold = float(value)

    # --- Document Text Extraction & Chunking ---
    def extract_text(self, file_path: str, doc_type: str) -> str:
        doc_type_clean = doc_type.lower().strip().replace(".", "")
        if doc_type_clean == "txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif doc_type_clean == "pdf":
            if pypdf is None:
                raise RuntimeError("pypdf is not installed in environment.")
            reader = pypdf.PdfReader(file_path)
            text_parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            return "\n".join(text_parts)

        elif doc_type_clean == "docx":
            if docx is None:
                raise RuntimeError("python-docx is not installed in environment.")
            doc_obj = docx.Document(file_path)
            return "\n".join([p.text for p in doc_obj.paragraphs if p.text])

        else:
            raise ValueError(f"Unsupported document type '{doc_type}'")

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        words = text.split()
        if not words:
            return []

        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += (chunk_size - overlap)
        return chunks

    # --- Indexing & Vectorization Pipeline ---
    def add_document(self, doc_id: str, file_path: str, filename: str, doc_type: str, scope: str, uploaded_by_user_id: int) -> Dict[str, Any]:
        if not self.is_initialized:
            self.initialize()

        logger.info(f"[POLICY RAG] Processing document upload: {filename} (ID: {doc_id}, Scope: {scope})")
        
        try:
            # 1. Extract text
            raw_text = self.extract_text(file_path, doc_type)
            if not raw_text or not raw_text.strip():
                raise ValueError("Document contains no readable text.")

            # 2. Chunk text
            chunks = self.chunk_text(raw_text)
            if not chunks:
                raise ValueError("Could not extract any chunks from document text.")

            logger.info(f"[POLICY RAG] Extracted {len(chunks)} chunks from {filename}")

            # 3. Generate Embeddings
            model = self._get_model()
            if model is None or faiss is None:
                raise RuntimeError("Embedding model or FAISS is unavailable.")

            embeddings = model.encode(chunks, normalize_embeddings=True) # Normalized for Cosine Similarity Inner Product
            embeddings_np = np.array(embeddings, dtype=np.float32)

            # 4. Add vectors to FAISS index & append chunk metadata
            start_index = len(self.chunks_metadata)
            self.index.add(embeddings_np)

            new_chunks_meta = []
            for idx, (chunk_str, emb) in enumerate(zip(chunks, embeddings)):
                meta_record = {
                    "global_index": start_index + idx,
                    "doc_id": doc_id,
                    "filename": filename,
                    "scope": scope,
                    "chunk_index": idx,
                    "text": chunk_str,
                    "embedding": emb.tolist() # Keep embedding list for atomic rebuilds
                }
                self.chunks_metadata.append(meta_record)
                new_chunks_meta.append(meta_record)

            # 5. Persist to disk
            self._save_index_and_metadata()

            # 6. Update Metadata DB
            metadata_service.update_policy_document_status(doc_id, "INDEXED", chunk_count=len(chunks))

            logger.info(f"[POLICY RAG] Document {filename} successfully indexed with {len(chunks)} chunks.")
            return {
                "success": True,
                "doc_id": doc_id,
                "status": "INDEXED",
                "chunk_count": len(chunks)
            }

        except Exception as e:
            logger.error(f"[POLICY RAG] Failed to index document {filename}: {e}")
            metadata_service.update_policy_document_status(doc_id, "FAILED", chunk_count=0)
            raise e

    def _save_index_and_metadata(self):
        self._ensure_directories()
        if self.index is not None and faiss is not None:
            faiss.write_index(self.index, FAISS_INDEX_PATH)

        with open(CHUNK_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(self.chunks_metadata, f, indent=2)

    # --- Document Deletion & Atomic Index Rebuild ---
    def delete_document(self, doc_id: str) -> bool:
        if not self.is_initialized:
            self.initialize()

        logger.info(f"[POLICY RAG] Deleting document ID: {doc_id}")

        # Filter out chunks belonging to this document
        remaining_chunks = [c for c in self.chunks_metadata if c["doc_id"] != doc_id]
        if len(remaining_chunks) == len(self.chunks_metadata):
            logger.warning(f"[POLICY RAG] Document ID {doc_id} not found in chunk metadata.")

        # Rebuild FAISS index from remaining chunk embeddings
        new_index = faiss.IndexFlatIP(EMBEDDING_DIM) if faiss is not None else None
        if remaining_chunks and new_index is not None:
            embeddings_list = [c["embedding"] for c in remaining_chunks]
            embeddings_np = np.array(embeddings_list, dtype=np.float32)
            new_index.add(embeddings_np)

        # Re-assign global indices
        for i, c in enumerate(remaining_chunks):
            c["global_index"] = i

        self.index = new_index
        self.chunks_metadata = remaining_chunks
        self._save_index_and_metadata()

        logger.info(f"[POLICY RAG] Rebuilt vector index. Remaining chunks: {len(self.chunks_metadata)}")
        return True

    # --- Single Policy Retrieval with Scope Filtering ---
    def retrieve_policy_context(self, query: str, active_db_id: Optional[str] = None, top_k: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieves top relevant policy chunks for query.
        Scope is backend-derived: GLOBAL + DATABASE:<active_db_id>
        Applies configurable similarity threshold. Diagnostic logging included.
        """
        if not self.is_initialized:
            self.initialize()

        if not self.chunks_metadata or self.index is None or self.index.ntotal == 0:
            logger.info("[POLICY RAG] Vector index empty. Returning no policy context.")
            return "", []

        model = self._get_model()
        if model is None:
            logger.warning("[POLICY RAG] Model unavailable. Returning no policy context.")
            return "", []

        # Derive target scopes on backend ONLY
        target_scopes = {"GLOBAL"}
        if active_db_id:
            target_scopes.add(f"DATABASE:{active_db_id}")

        logger.info(f"[POLICY RAG] Executing retrieval for Query: '{query}' | Active DB: '{active_db_id}' | Allowed Scopes: {target_scopes}")

        # Encode query
        query_emb = model.encode([query], normalize_embeddings=True)
        query_emb_np = np.array(query_emb, dtype=np.float32)

        # Search top candidate vectors (retrieve more to allow scope filtering)
        search_k = min(top_k * 4, self.index.ntotal)
        distances, indices = self.index.search(query_emb_np, search_k)

        accepted_chunks = []
        diagnostics = []

        rank = 1
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks_metadata):
                continue

            chunk_meta = self.chunks_metadata[idx]
            scope = chunk_meta.get("scope", "GLOBAL")
            score = float(dist)

            # Check Scope Match
            if scope not in target_scopes:
                logger.debug(f"[POLICY RAG] Candidate rank {rank} (Score: {score:.3f}, Doc: {chunk_meta['filename']}) rejected: Scope '{scope}' not in active scopes.")
                continue

            # Check Distance / Similarity Threshold
            is_accepted = (score >= self.threshold)
            status_str = "ACCEPTED" if is_accepted else f"REJECTED (Score {score:.3f} < Threshold {self.threshold:.3f})"

            logger.info(
                f"[POLICY RAG] Candidate Rank {rank} | Doc: '{chunk_meta['filename']}' | "
                f"Chunk: #{chunk_meta['chunk_index']} | Score: {score:.4f} | Status: {status_str}"
            )

            diag_item = {
                "rank": rank,
                "document": chunk_meta["filename"],
                "chunk_index": chunk_meta["chunk_index"],
                "score": score,
                "scope": scope,
                "status": status_str
            }
            diagnostics.append(diag_item)

            if is_accepted:
                accepted_chunks.append(chunk_meta)
                if len(accepted_chunks) >= top_k:
                    break

            rank += 1

        if not accepted_chunks:
            logger.info(f"[POLICY RAG] Zero chunks met threshold ({self.threshold}). Returning empty context.")
            return "", diagnostics

        # Format policy context string with strict XML-like data delimiters
        formatted_chunks = []
        for c in accepted_chunks:
            chunk_block = (
                f"[POLICY CONTEXT - DATA ONLY]\n"
                f"Source Document: {c['filename']} (Scope: {c['scope']}, Chunk #{c['chunk_index']})\n"
                f"Content:\n{c['text']}\n"
                f"[/POLICY CONTEXT]"
            )
            formatted_chunks.append(chunk_block)

        formatted_policy_context = "\n\n".join(formatted_chunks)
        logger.info(f"[POLICY RAG] Formatted {len(accepted_chunks)} policy chunk(s) for LLM context.")
        return formatted_policy_context, diagnostics

policy_rag_service = PolicyRAGService()
