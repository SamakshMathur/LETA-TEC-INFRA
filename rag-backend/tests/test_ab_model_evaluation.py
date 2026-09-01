import unittest
from unittest.mock import MagicMock, patch
import app.generation.synthesizer as synth
from app.api.app import compute_context_fingerprint

class TestABModelEvaluation(unittest.TestCase):
    
    def setUp(self):
        pass

    @patch("app.generation.synthesizer.ANSWER_LLM_PROVIDER", "anthropic")
    @patch("app.generation.synthesizer.CLAUDE_MAIN_MODEL", "claude-sonnet-test")
    @patch("app.generation.synthesizer._estimate_complexity", return_value=1.0)
    @patch("app.generation.clients.get_claude_client")
    def test_provider_anthropic_selects_anthropic(self, mock_get_claude, mock_estimate):
        mock_claude = MagicMock()
        mock_get_claude.return_value = mock_claude
        mock_event = MagicMock()
        mock_event.type = "content_block_delta"
        mock_event.delta.type = "text_delta"
        mock_event.delta.text = "Hello Claude"
        
        mock_stream = MagicMock()
        mock_stream.__enter__.return_value = [mock_event]
        mock_claude.messages.stream.return_value = mock_stream
        
        result = synth.synthesize_answer("What is the GST rate?", "Some context")
        
        self.assertEqual(result, "Hello Claude")
        mock_claude.messages.stream.assert_called_once()
        self.assertEqual(mock_claude.messages.stream.call_args[1]["model"], "claude-sonnet-test")

    @patch("app.generation.synthesizer.ANSWER_LLM_PROVIDER", "openai")
    @patch("app.generation.synthesizer.ANSWER_LLM_MODEL", "gpt-4o-test")
    @patch("app.generation.clients.get_openai_client")
    def test_provider_openai_selects_openai(self, mock_get_client):
        mock_oai = MagicMock()
        mock_get_client.return_value = mock_oai
        mock_chunk = MagicMock()
        mock_chunk.usage = None
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Hello OpenAI"
        
        mock_oai.chat.completions.create.return_value = [mock_chunk]
        
        result = synth.synthesize_answer("What is the GST rate?", "Some context")
        
        self.assertEqual(result, "Hello OpenAI")
        mock_oai.chat.completions.create.assert_called_once()
        self.assertEqual(mock_oai.chat.completions.create.call_args[1]["model"], "gpt-4o-test")

    @patch("app.generation.synthesizer.ANSWER_LLM_PROVIDER", "openai")
    @patch("app.generation.clients.get_openai_client")
    @patch("app.generation.clients.get_claude_client")
    def test_openai_failure_no_fallback_to_claude(self, mock_get_claude, mock_get_openai):
        mock_oai = MagicMock()
        mock_get_openai.return_value = mock_oai
        mock_oai.chat.completions.create.side_effect = Exception("OpenAI API Down")
        
        with self.assertRaises(RuntimeError) as context:
            synth.synthesize_answer("What is the GST rate?", "Some context")
            
        self.assertIn("OpenAI-compatible generation error", str(context.exception))
        mock_get_claude.assert_not_called()

    @patch("app.generation.synthesizer.ANSWER_LLM_PROVIDER", "anthropic")
    @patch("app.generation.clients.get_claude_client")
    @patch("app.generation.clients.get_openai_client")
    def test_anthropic_failure_no_fallback_to_openai(self, mock_get_openai, mock_get_claude):
        mock_claude = MagicMock()
        mock_get_claude.return_value = mock_claude
        mock_claude.messages.stream.side_effect = Exception("Claude API Down")
        
        result = synth.synthesize_answer("What is the GST rate?", "Some context")
        
        self.assertIn("Error generating answer", result)
        mock_get_openai.assert_not_called()

    def test_context_fingerprint_identical_across_runs(self):
        question = "What is section 16?"
        chunks = [
            {"source": "doc1.pdf", "page": 1, "text": "ITC eligibility details..."},
            {"source": "doc2.pdf", "page": 2, "text": "Apportionment of credit..."}
        ]
        context = "ITC eligibility details...\nApportionment of credit..."
        
        fp_anthropic = compute_context_fingerprint(question, chunks, context, "anthropic", "claude-sonnet")
        fp_openai = compute_context_fingerprint(question, chunks, context, "openai", "gpt-4o")
        
        self.assertEqual(fp_anthropic["context_hash"], fp_openai["context_hash"])
        self.assertEqual(fp_anthropic["chunk_identifiers"], fp_openai["chunk_identifiers"])
        self.assertEqual(fp_anthropic["chunk_hashes"], fp_openai["chunk_hashes"])
        self.assertEqual(fp_anthropic["fingerprint_hash"], fp_openai["fingerprint_hash"])
        
        self.assertEqual(fp_anthropic["answer_provider"], "anthropic")
        self.assertEqual(fp_anthropic["answer_model"], "claude-sonnet")
        self.assertEqual(fp_openai["answer_provider"], "openai")
        self.assertEqual(fp_openai["answer_model"], "gpt-4o")

    @patch("app.generation.clients.get_openai_client")
    @patch("app.generation.clients.get_claude_client")
    def test_refinement_and_generation_use_openai_exclusively(self, mock_get_claude, mock_get_openai):
        # Setup mock OpenAI client
        mock_oai = MagicMock()
        mock_get_openai.return_value = mock_oai
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = '{"queries": ["GST cars"], "hyde_document": "Hyde doc", "topic": "ITC", "subtopic": null}'
        mock_oai.chat.completions.create.return_value = [mock_chunk]
        
        # Test Query Refinement
        from app.retrieval.query_refiner import generate_advanced_queries
        generate_advanced_queries("GST on cars", provider="openai")
        
        # Test Synthesizer Answer Generation
        synth.synthesize_answer("GST on cars", "Context text", provider="openai")
        
        # Assert Claude client is never called / initialized
        mock_get_claude.assert_not_called()
        # Assert OpenAI client is called
        mock_get_openai.assert_called()

    @patch("app.generation.clients.get_openai_client")
    @patch("app.generation.clients.get_claude_client")
    @patch("app.generation.synthesizer._estimate_complexity", return_value=1.0)
    def test_refinement_and_generation_use_anthropic_exclusively(self, mock_complexity, mock_get_claude, mock_get_openai):
        # Setup mock Claude client
        mock_claude = MagicMock()
        mock_get_claude.return_value = mock_claude
        
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock()]
        mock_msg.content[0].text = '{"queries": ["GST cars"], "hyde_document": "Hyde doc", "topic": "ITC", "subtopic": null}'
        mock_claude.messages.create.return_value = mock_msg
        
        mock_event = MagicMock()
        mock_event.type = "content_block_delta"
        mock_event.delta.type = "text_delta"
        mock_event.delta.text = "Answer content"
        mock_stream = MagicMock()
        mock_stream.__enter__.return_value = [mock_event]
        mock_claude.messages.stream.return_value = mock_stream
        
        # Test Query Refinement
        from app.retrieval.query_refiner import generate_advanced_queries
        generate_advanced_queries("GST on cars", provider="anthropic")
        
        # Test Synthesizer Answer Generation
        synth.synthesize_answer("GST on cars", "Context text", provider="anthropic")
        
        # Assert OpenAI client is never called / initialized
        mock_get_openai.assert_not_called()
        # Assert Claude client is called
        mock_get_claude.assert_called()

    @patch("app.generation.clients.OPENAI_API_KEY", "")
    def test_missing_openai_credentials_fails_visibly(self):
        from app.generation.clients import get_openai_client
        with self.assertRaises(ValueError) as context:
            get_openai_client()
        self.assertIn("OPENAI_API_KEY", str(context.exception))

    @patch("app.generation.clients.ANTHROPIC_API_KEY", "")
    def test_missing_anthropic_credentials_fails_visibly(self):
        from app.generation.clients import get_claude_client
        with self.assertRaises(ValueError) as context:
            get_claude_client()
        self.assertIn("ANTHROPIC_API_KEY", str(context.exception))
