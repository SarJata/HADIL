import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from unittest.mock import MagicMock

class DummyModel:
    def encode(self, texts, normalize_embeddings=True):
        vecs = []
        for t in texts:
            if "cake" in t.lower() or "recipe" in t.lower():
                v = np.zeros(384, dtype=np.float32)
                v[0] = -1.0
            else:
                v = np.ones(384, dtype=np.float32)
                v = v / np.linalg.norm(v)
            vecs.append(v)
        return np.array(vecs, dtype=np.float32)

class DummyFAISSIndex:
    def __init__(self, dim):
        self.dim = dim
        self.vectors = []
        self.ntotal = 0

    def add(self, vecs):
        for v in vecs:
            self.vectors.append(v)
        self.ntotal = len(self.vectors)

    def search(self, query_vec, top_k):
        if not self.vectors:
            return np.array([[]]), np.array([[]])
        q = query_vec[0]
        scores = [float(np.dot(q, v)) for v in self.vectors]
        indexed_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        indices = [x[0] for x in indexed_scores]
        distances = [x[1] for x in indexed_scores]
        return np.array([distances], dtype=np.float32), np.array([indices], dtype=np.int64)

from services.policy_rag_service import policy_rag_service, PolicyRAGService
from services.metadata_service import metadata_service
import services.policy_rag_service as prs

class TestPolicyRAGSubsystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        prs.faiss = MagicMock()
        prs.faiss.IndexFlatIP = DummyFAISSIndex
        cls.service = PolicyRAGService()
        cls.service.model = DummyModel()
        cls.service.index = DummyFAISSIndex(384)
        cls.service._get_model = lambda: cls.service.model
        cls.service.is_initialized = True
        cls.service.threshold = 0.50
        
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)

    def test_01_text_chunking(self):
        text = "word " * 1200 # 1200 words
        chunks = self.service.chunk_text(text, chunk_size=500, overlap=50)
        self.assertGreater(len(chunks), 2)
        self.assertIn("word", chunks[0])

    def test_02_extraction_txt(self):
        txt_path = os.path.join(self.temp_dir, "policy.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Company Policy: Data retention is strictly 7 years for financial records.")

        extracted = self.service.extract_text(txt_path, "txt")
        self.assertIn("financial records", extracted)

    def test_03_vector_indexing_and_retrieval(self):
        # Create temp text file
        doc_path = os.path.join(self.temp_dir, "retention_policy.txt")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("Employees must retain customer sales records for exactly 5 years. Deleting active accounts is prohibited.")

        doc_id = "test_doc_001"
        res = self.service.add_document(
            doc_id=doc_id,
            file_path=doc_path,
            filename="retention_policy.txt",
            doc_type="txt",
            scope="GLOBAL",
            uploaded_by_user_id=1
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "INDEXED")

        # Test relevant retrieval
        context, diag = self.service.retrieve_policy_context("How long to keep sales records?", active_db_id="sales.db")
        self.assertIn("retention_policy.txt", context)
        self.assertIn("5 years", context)

        # Test irrelevant retrieval rejected by threshold
        context_irrelevant, diag_irr = self.service.retrieve_policy_context("What is the recipe for chocolate cake?", active_db_id="sales.db")
        self.assertEqual(context_irrelevant, "")

    def test_04_scope_isolation(self):
        doc_path = os.path.join(self.temp_dir, "chinook_private.txt")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("Chinook specific rule: All album deletions require explicit manager signoff.")

        self.service.add_document(
            doc_id="test_doc_002",
            file_path=doc_path,
            filename="chinook_private.txt",
            doc_type="txt",
            scope="DATABASE:chinook.db",
            uploaded_by_user_id=1
        )

        # Query when active DB is sales.db -> Should NOT retrieve chinook policy
        ctx_sales, _ = self.service.retrieve_policy_context("Album deletion rules", active_db_id="sales.db")
        self.assertNotIn("chinook_private.txt", ctx_sales)

        # Query when active DB is chinook.db -> SHOULD retrieve chinook policy
        ctx_chinook, _ = self.service.retrieve_policy_context("Album deletion rules", active_db_id="chinook.db")
        self.assertIn("chinook_private.txt", ctx_chinook)

    def test_05_deletion_rebuilds_index(self):
        initial_chunks = len(self.service.chunks_metadata)
        self.service.delete_document("test_doc_001")
        remaining_chunks = len(self.service.chunks_metadata)
        self.assertLess(remaining_chunks, initial_chunks)

        # Verify test_doc_001 content is no longer retrievable
        ctx, _ = self.service.retrieve_policy_context("How long to keep sales records?", active_db_id="sales.db")
        self.assertNotIn("retention_policy.txt", ctx)

if __name__ == "__main__":
    unittest.main()
