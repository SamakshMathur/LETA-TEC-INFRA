import pytest
from unittest.mock import patch, MagicMock
from app.generation.synthesizer import (
    _stream_claude,
    synthesize_answer_stream,
    CLAUDE_THINKING_BUDGET
)
from app.generation.validator import validate_answer_integrity
from app.api.app import ask_question_sync

def test_stream_claude_usage_tracker_propagation():
    """Verify that usage_tracker dictionary is mutably updated in _stream_claude."""
    usage_tracker = {}
    mock_client = MagicMock()
    mock_stream = MagicMock()
    
    mock_event = MagicMock()
    mock_event.type = "content_block_delta"
    mock_event.delta.type = "text_delta"
    mock_event.delta.text = "Hello world"
    
    # Mock context manager stream to return mock_stream
    mock_stream.__enter__.return_value = mock_stream
    mock_stream.__iter__.return_value = iter([mock_event])
    
    mock_final_msg = MagicMock()
    mock_final_msg.usage.input_tokens = 120
    mock_final_msg.usage.output_tokens = 45
    mock_stream.get_final_message.return_value = mock_final_msg
    
    mock_client.messages.stream.return_value = mock_stream
    
    with patch("app.generation.clients.get_claude_client", return_value=mock_client):
        # Consume the generator to trigger the code execution
        chunks = list(_stream_claude(
            question="What is GST?",
            system_prompt="Instruction",
            use_haiku=True,
            use_thinking=False,
            usage_tracker=usage_tracker
        ))
        
        assert "".join(chunks) == "Hello world"
        assert usage_tracker.get("input_tokens") == 120
        assert usage_tracker.get("output_tokens") == 45


def test_thinking_budget_override_constraints():
    """Verify thinking_budget Y = max(1024, min(CLAUDE_THINKING_BUDGET, resolved_max_tokens)) constraint."""
    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_stream.__enter__.return_value = mock_stream
    mock_stream.__iter__.return_value = iter([])
    mock_client.messages.stream.return_value = mock_stream
    
    with patch("app.generation.clients.get_claude_client", return_value=mock_client):
        # 1. Test case: resolved_max_tokens = 2000 (standard). Y should be min(5000, 2000) = 2000. max_tokens = 4000.
        list(_stream_claude(
            question="What is GST?",
            system_prompt="Instruction",
            use_haiku=False,
            use_thinking=True,
            max_tokens_override=2000
        ))
        
        args, kwargs = mock_client.messages.stream.call_args
        assert kwargs["thinking"]["budget_tokens"] == 2000
        assert kwargs["max_tokens"] == 4000
        
        # 2. Test case: resolved_max_tokens = 800 (brief). Y should be max(1024, min(5000, 800)) = 1024. max_tokens = 1824.
        list(_stream_claude(
            question="What is GST?",
            system_prompt="Instruction",
            use_haiku=False,
            use_thinking=True,
            max_tokens_override=800
        ))
        
        args, kwargs = mock_client.messages.stream.call_args
        assert kwargs["thinking"]["budget_tokens"] == 1024
        assert kwargs["max_tokens"] == 1824


def test_validator_metrics_instrumentation():
    """Verify that validate_answer_integrity instruments timing, counts, and failure categories."""
    content = "Under Section 9 of CGST Act, 2017, the tax rate is 18%. But Notification 12/2017 specifies otherwise."
    chunks = [
        {
            "text": "Section 9: Levy and collection of CGST",
            "page": 1,
            "metadata": {
                "rel_path": "CGST_Act.pdf",
                "citations": ["sec_9"],
                "provisions": ["section 9"]
            }
        },
        {
            "text": "Notification 12/2017-Central Tax (Rate) exempts certain services.",
            "page": 2,
            "metadata": {
                "rel_path": "notif_12_2017.pdf",
                "citations": ["12/2017-Central"],
                "provisions": ["notification 12/2017"]
            }
        }
    ]
    
    # Mock NLI cross-encoder
    mock_verifier = MagicMock()
    mock_verifier.load_failed = False
    mock_verifier.model = MagicMock()
    mock_verifier.verify_batch.return_value = ["SUPPORTED", "SUPPORTED"]
    
    with patch("app.generation.validator.verifier", mock_verifier):
        res = validate_answer_integrity(content, chunks, is_strict=True)
        
        # Verify counts
        assert res["citation_count"] >= 2
        assert res["NLI_pairs_after_pruning"] >= 0
        assert "total_validation_ms" in res
        assert "model_load_ms" in res
        assert "NLI_inference_ms" in res
        assert "failure_categories" in res


@pytest.mark.anyio
async def test_repair_safeguard_fail_closed_mechanism():
    """Verify that ask_question_sync fails closed immediately for unrepairable errors."""
    question = "Draft a reply for denying ITC under Section 16"
    
    # Mock semantic cache hit to False
    mock_cache_lookup = MagicMock(return_value=None)
    
    # Mock query topic classification rules (None to trigger fallback)
    mock_classify_rules = MagicMock(return_value={"topic": None, "subtopic": None})
    
    # Mock extract_query_topic to return Topic
    mock_extract_topic = MagicMock(return_value={"topic": "ITC", "subtopic": "Availability"})
    
    # Mock RAG retrieval chunks
    mock_chunks = [
        {
            "text": "CGST Section 16 deals with input tax credit conditions.",
            "source": "CGST_Act.pdf",
            "metadata": {"rel_path": "CGST_Act.pdf", "citations": ["16(2)"], "provisions": ["16"]}
        }
    ]
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = mock_chunks
    
    # Mock initial answer generation which hallucinated Section 75(1)
    mock_synth = MagicMock(side_effect=lambda *args, **kwargs: ["Section 75(1) must apply."])
    
    # Mock validate_answer_integrity to return UNVERIFIED citation for Section 75(1)
    mock_val_res = {
        "is_valid": False,
        "warnings": ["Unverified Citation: '75(1)' is cited but not present in the retrieved evidence."],
        "citations_status": {"75(1)": "UNVERIFIED"},
        "ungrounded_numbers": [],
        "severity": "HIGH",
        "citation_count": 1,
        "unique_claim_count": 1,
        "NLI_pairs_before_pruning": 1,
        "NLI_pairs_after_pruning": 1,
        "model_load_ms": 0.1,
        "NLI_inference_ms": 1.0,
        "total_validation_ms": 1.5,
        "failure_categories": ["UNVERIFIED_CITATION"],
    }
    
    # Mock validate_answer_integrity import
    with patch("app.cache.cache_lookup", mock_cache_lookup), \
         patch("app.retrieval.query_refiner.classify_topic_rules", mock_classify_rules), \
         patch("app.retrieval.query_refiner.extract_query_topic", mock_extract_topic), \
         patch("app.api.app.get_retriever", return_value=mock_retriever), \
         patch("app.api.app.check_and_escalate_evidence", return_value=(mock_chunks, True, [])), \
         patch("app.generation.synthesizer.synthesize_answer_stream", mock_synth), \
         patch("app.generation.validator.validate_answer_integrity", return_value=mock_val_res), \
         patch("app.retrieval.retriever.embed_query", return_value=[0.1]*1024):

             
        # Mock request payload
        from fastapi import Request
        from app.api.app import QuestionRequest
        mock_req = QuestionRequest(question=question, session_id="test_sess")
        
        # We mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state = MagicMock()
        mock_request.state.query_id = "test_query"
        
        # Make request to ask_question_sync (which should fail closed immediately without calling _gen_repair)
        with patch("asyncio.to_thread", side_effect=lambda f: f()):
            resp = await ask_question_sync(mock_request, mock_req)
            
            # Extract JSON content
            import json
            body = json.loads(resp.body)
            
            assert "I cannot sufficiently verify this answer" in body["answer"]
            assert "Unverified Citations (absent from source files): `75(1)`" in body["answer"]
            # Validate that the repair generation ms was 0.0, meaning the repair call was skipped!
            assert body["metrics"]["repair_generation_ms"] == 0.0
