import os
import sys

# Override DATA_DIR at the very top to prevent loading paths outside the workspace
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATA_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RAG_INFORMATION_DATABASE"))

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

# Pre-mock Redis to avoid connection failures
sys.modules["redis"] = MagicMock()

# Mock Database before importing app
import app.database
app.database.db.client = MagicMock()
app.database.db.connect = MagicMock()

# Mock app.cache to avoid actual Redis/DiskCache lookups
import app.cache
app.cache._get_redis = MagicMock(return_value=None)
app.cache._get_disk_cache = MagicMock(return_value=None)

# Mock documents BASE_DIR / get_activity_feed to avoid accessing files outside workspace
import app.api.documents
app.api.documents.get_activity_feed = MagicMock(return_value=[])

# Mock embed_query and model loader to avoid loading the Hugging Face model
import app.retrieval.retriever
app.retrieval.retriever.embed_query = MagicMock(return_value=np.zeros(1024))
app.retrieval.retriever.get_model = MagicMock()

# Mock query expansion and LLM classification in query_refiner to avoid Anthropic API calls
import app.retrieval.query_refiner
def mock_generate_advanced_queries(raw_query, *args, **kwargs):
    return {
        "queries": [raw_query, raw_query, raw_query],
        "hyde_document": "This is a hypothetical document.",
        "topic": "Valuation",
        "subtopic": "Discounts"
    }
app.retrieval.query_refiner.generate_advanced_queries = mock_generate_advanced_queries

# Import dependencies and create mock retriever
import app.dependencies
app.dependencies.preload_all_models = MagicMock()
mock_retriever = MagicMock()
mock_retriever.index = MagicMock()

# Mock search and supplement_and_rerank methods to return a dummy list of matched chunks
mock_chunks = [
    {
        "text": "CGST Act Section 15 deals with valuation of taxable supply.",
        "rel_path": "Act/CGST ACT.docx",
        "provisions": ["CGST_SEC_15", "CGST_SEC_15_3"],
        "_is_statute_first": True,
        "_statute_priority": 1.0
    }
]
mock_retriever.search.return_value = mock_chunks
mock_retriever.supplement_and_rerank.return_value = mock_chunks

# Set the global retriever instance
app.dependencies._retriever = mock_retriever

# Import FastAPI TestClient
from fastapi.testclient import TestClient

from app.api.app import app

class TestAskIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.generation.synthesizer.synthesize_answer_stream")
    def test_ask_sync_success(self, mock_synth):
        # Mock LLM stream generator synchronously
        def mock_generator(*args, **kwargs):
            yield "This is a mocked answer for Section 15 CGST Act."
        mock_synth.side_effect = mock_generator

        response = self.client.post(
            "/ask-sync",
            json={
                "question": "What are the rules for valuation under Section 15 CGST?",
                "session_id": "test_session_123"
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)
        self.assertIn("mocked", data["answer"])
        self.assertIn("sources", data)
        self.assertEqual(data["sources"][0]["title"], "CGST ACT.docx")

    @patch("app.generation.synthesizer.synthesize_answer_stream")
    def test_ask_streaming_success(self, mock_synth):
        # Mock LLM stream generator synchronously yielding raw text chunks
        def mock_generator(*args, **kwargs):
            yield "This "
            yield "is "
            yield "a "
            yield "mocked "
            yield "answer."
        mock_synth.side_effect = mock_generator

        response = self.client.post(
            "/ask",
            json={
                "question": "Secondary discounts under Section 15(3) CGST.",
                "session_id": "test_session_123"
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")

        # Read stream response body
        content = response.text
        self.assertIn("mocked", content)
        self.assertIn("answer", content)

if __name__ == "__main__":
    unittest.main()
