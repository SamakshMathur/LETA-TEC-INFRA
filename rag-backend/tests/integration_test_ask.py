import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.api.app import app
import app.dependencies
import app.retrieval.retriever
import app.retrieval.query_refiner


class TestAskIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._orig_retriever = app.dependencies._retriever

        self.mock_retriever = MagicMock()
        self.mock_retriever.index = MagicMock()
        self.mock_chunks = [
            {
                "text": "CGST Act Section 15 deals with valuation of taxable supply.",
                "rel_path": "Act/CGST ACT.docx",
                "provisions": ["CGST_SEC_15", "CGST_SEC_15_3"],
                "_is_statute_first": True,
                "_statute_priority": 1.0
            }
        ]
        self.mock_retriever.search.return_value = self.mock_chunks
        self.mock_retriever.supplement_and_rerank.return_value = self.mock_chunks
        app.dependencies._retriever = self.mock_retriever

        self.patcher_adv = patch("app.retrieval.query_refiner.generate_advanced_queries", return_value={
            "queries": ["q", "q", "q"],
            "hyde_document": "This is a hypothetical document.",
            "topic": "Valuation",
            "subtopic": "Discounts"
        })
        self.patcher_adv.start()

    def tearDown(self):
        app.dependencies._retriever = self._orig_retriever
        self.patcher_adv.stop()

    @patch("app.generation.synthesizer.synthesize_answer_stream")
    def test_ask_sync_success(self, mock_synth):
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

        content = response.text
        self.assertIn("mocked", content)
        self.assertIn("answer", content)


if __name__ == "__main__":
    unittest.main()
