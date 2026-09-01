import unittest
from unittest.mock import patch, MagicMock
from app.generation.validator import validate_answer_integrity

class TestLayeredValidator(unittest.TestCase):
    def setUp(self):
        # We define a standard set of mock chunks representing Acts and Circulars
        self.mock_chunks = [
            {
                "text": "Section 16(2) CGST Act mandates tax invoice possession for claiming input tax credit.",
                "metadata": {
                    "rel_path": "statutes/cgst_act.pdf",
                    "document_type": "PRIMARY_LAW",
                    "citations": ["CGST_SEC_16_2"],
                    "provisions": ["CGST_SEC_16_2"],
                    "year": 2017
                }
            },
            {
                "text": "Circular No. 105/2019 clarifies Section 16(2) discount treatment and ITC eligibility.",
                "metadata": {
                    "rel_path": "circulars/circular_105.pdf",
                    "document_type": "CIRCULAR",
                    "citations": ["CIRCULAR_105", "CGST_SEC_16_2"],
                    "provisions": ["CIRCULAR_105", "CGST_SEC_16_2"],
                    "year": 2019
                }
            },
            {
                "text": "Circular No. 92/2019 clarifies post-sale promotional scheme distributions.",
                "metadata": {
                    "rel_path": "circulars/circular_92.pdf",
                    "document_type": "CIRCULAR",
                    "citations": ["CIRCULAR_92"],
                    "provisions": ["CIRCULAR_92"],
                    "year": 2019
                }
            },
            {
                "text": "Circular No. 200/2024 provides updated clarifications on Section 16(2) invoice compliance rules.",
                "metadata": {
                    "rel_path": "circulars/circular_200.pdf",
                    "document_type": "CIRCULAR",
                    "citations": ["CIRCULAR_200", "CGST_SEC_16_2"],
                    "provisions": ["CIRCULAR_200", "CGST_SEC_16_2"],
                    "year": 2024
                }
            }
        ]

    def test_layer_a_extraction(self):
        content = "As per Section 16(2) and Circular 105, credit is allowed."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertIn("16(2)", res["citations_status"])
        self.assertIn("105", res["citations_status"])

    def test_layer_b_existence_in_source_packet(self):
        content = "Under Section 16(2), invoice is required."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(res["citations_status"]["16(2)"], "EXACT")

    def test_layer_c_authority_presence_in_source_text(self):
        content = "Section 16(2) is active."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(res["citations_status"]["16(2)"], "EXACT")

    def test_layer_d_source_type_mismatch(self):
        content = "Section 105 of the CGST Act mandates that all trade discounts are taxable."
        res = validate_answer_integrity(content, self.mock_chunks)
        any_mismatch = any("Authority Mismatch" in w for w in res["warnings"])
        self.assertTrue(any_mismatch)

    def test_layer_e_semantic_contradiction(self):
        content = "Under Section 16(2), invoices are completely optional."
        with patch('app.generation.validator.verifier.verify', return_value="CONTRADICTED"):
            res = validate_answer_integrity(content, self.mock_chunks)
            any_contradiction = any("Contradiction" in w for w in res["warnings"])
            self.assertTrue(any_contradiction)
            self.assertEqual(res["severity"], "HIGH")
            self.assertFalse(res["is_valid"])

    def test_layer_e_semantic_support(self):
        content = "Section 16(2) invoice is required."
        with patch('app.generation.validator.verifier.verify', return_value="SUPPORTED"):
            res = validate_answer_integrity(content, self.mock_chunks)
            any_unverified = any("Unverified Claim" in w for w in res["warnings"])
            self.assertFalse(any_unverified)

    def test_layer_e_cleans_markdown_headers_and_points(self):
        content = "[POINT 1/3] **IMPORTANT CLAUSE**: Section 16(2) invoice is required. [📄 View](file:///mock/path.pdf)"
        with patch('app.generation.validator.verifier.verify', return_value="SUPPORTED") as mock_verify:
            res = validate_answer_integrity(content, self.mock_chunks)
            mock_verify.assert_any_call("IMPORTANT CLAUSE: Section 16(2) invoice is required.", "Section 16(2) CGST Act mandates tax invoice possession for claiming input tax credit.")
            self.assertTrue(res["is_valid"])

    def test_layer_e_unrelated_chunks_do_not_cause_false_contradiction(self):
        content = "Section 16(2) CGST Act mandates tax invoice possession."
        
        def mock_verify_side_effect(claim, premise):
            if "cgst_act.pdf" in premise or "mandates tax invoice" in premise:
                return "SUPPORTED"
            return "UNKNOWN"
            
        with patch('app.generation.validator.verifier.verify', side_effect=mock_verify_side_effect):
            res = validate_answer_integrity(content, self.mock_chunks)
            any_unverified = any("Unverified Claim" in w for w in res["warnings"])
            self.assertFalse(any_unverified)
            self.assertTrue(res["is_valid"])

    def test_layer_f_temporal_check_warning(self):
        content = "In 2017, Circular 105 resolved all discount calculations."
        res = validate_answer_integrity(content, self.mock_chunks)
        any_temporal = any("Temporal Check" in w for w in res["warnings"])
        self.assertTrue(any_temporal)
        self.assertEqual(res["severity"], "MEDIUM")
        self.assertTrue(res["is_valid"])

    def test_layer_g_related_higher_authority_warning(self):
        content = "Circular 105 allows post-sale trade discounts."
        res = validate_answer_integrity(content, self.mock_chunks)
        any_conflict = any("may be overridden by primary law 'cgst_act.pdf'" in w for w in res["warnings"])
        self.assertTrue(any_conflict)

    def test_layer_g_unrelated_higher_authority_no_warning(self):
        content = "Circular 92 explains promotional items distribution."
        res = validate_answer_integrity(content, self.mock_chunks)
        any_conflict = any("may be overridden by primary law" in w for w in res["warnings"])
        self.assertFalse(any_conflict)

    def test_layer_g_related_newer_source_warning(self):
        content = "Circular 105 allows post-sale trade discounts."
        res = validate_answer_integrity(content, self.mock_chunks)
        any_supersede = any("Newer source 'circular_200.pdf' (2024) may supersede 'circular_105.pdf'" in w for w in res["warnings"])
        self.assertTrue(any_supersede)

    def test_layer_g_unrelated_newer_source_no_warning(self):
        content = "Circular 92 explains promotional items distribution."
        res = validate_answer_integrity(content, self.mock_chunks)
        any_supersede = any("may supersede 'circular_92.pdf'" in w for w in res["warnings"])
        self.assertFalse(any_supersede)

    def test_numeric_grounding_excludes_citation_identifiers(self):
        content = "Refer to Circular No. 105/2019 and Section 16(2) and document reference 217/11/2024-GST."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(len(res["ungrounded_numbers"]), 0)
        self.assertTrue(res["is_valid"])

    def test_real_numeric_claims_remain_validated(self):
        # Substantive numbers like tax rates (e.g. 18% or 28%) and monetary amounts (e.g. ₹20,00,000) must still trigger warnings if ungrounded
        content = "The applicable rate is 18% and the threshold is ₹20,00,000."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertIn("18%", res["ungrounded_numbers"])
        self.assertIn("₹20,00,000", res["ungrounded_numbers"])
        any_ungrounded = any("Ungrounded statutory parameter" in w or "Ungrounded number" in w for w in res["warnings"])
        self.assertTrue(any_ungrounded)

    def test_unmatched_citation_does_not_fallback(self):
        # A completely unmatched citation must remain UNVERIFIED and not fall back to chunks[0]
        content = "Section 999 is cited here."
        res = validate_answer_integrity(content, self.mock_chunks)
        self.assertEqual(res["citations_status"]["999"], "UNVERIFIED")
        any_unverified = any("Unverified Citation: '999'" in w for w in res["warnings"])
        self.assertTrue(any_unverified)

    def test_all_relevant_matching_chunks_collected(self):
        # For Section 16(2), three matching chunks (cgst_act.pdf, circular_105.pdf, circular_200.pdf) should be collected.
        # We verify that during validation, the verifier is called for chunks in matching_chunks.
        content = "Section 16(2) rules apply."
        with patch('app.generation.validator.verifier.verify', return_value="UNKNOWN") as mock_verify:
            res = validate_answer_integrity(content, self.mock_chunks)
            # Should be verified against all 3 matching chunks for Section 16(2)
            self.assertEqual(mock_verify.call_count, 3)

    def test_q10_logger_exception_path_no_nameerror(self):
        # Simulate ask_question_sync validation exception path to ensure it uses logger and does not raise NameError.
        import sys
        orig_synth = sys.modules.get('app.generation.synthesizer')
        
        mock_var = MagicMock()
        mock_var.get = MagicMock(return_value=0)
        
        mock_synth = MagicMock()
        mock_synth.synthesize_answer_stream = MagicMock(return_value=["A mock answer."])
        mock_synth._estimate_complexity = MagicMock(return_value=0.1)
        mock_synth.input_tokens_var = mock_var
        mock_synth.output_tokens_var = mock_var
        sys.modules['app.generation.synthesizer'] = mock_synth
        
        try:
            from fastapi.testclient import TestClient
            if isinstance(TestClient, MagicMock):
                # Skip integration test in mocked/restricted environments
                return
            from app.api.app import app
            client = TestClient(app)
            
            # Patch validate_answer_integrity to raise an exception
            with patch('app.generation.validator.validate_answer_integrity', side_effect=Exception("Simulated validation error")):
                with patch('app.api.app.logger.warning') as mock_logger_warning:
                    with patch('app.api.app.get_retriever') as mock_get_ret:
                        mock_ret = MagicMock()
                        mock_ret.search.return_value = []
                        mock_get_ret.return_value = mock_ret
                        
                        with patch('app.ai_logger.commit_ai_log'), \
                             patch('app.ai_logger.init_ai_log'), \
                             patch('app.ai_logger.update_ai_log'):
                             
                            response = client.post(
                                "/ask-sync",
                                json={
                                    "question": "What is tax recovery?",
                                    "history": [],
                                    "is_draft": False
                                }
                            )
                            self.assertEqual(response.status_code, 200)
                            mock_logger_warning.assert_called_with("Post-gen validation failed: Simulated validation error")
        finally:
            if orig_synth:
                sys.modules['app.generation.synthesizer'] = orig_synth
            else:
                sys.modules.pop('app.generation.synthesizer', None)

    def test_structured_citation_and_numeric_grounding_audit_fixes(self):
        # 1. Section 16(2) does not match Section 116, 2016, or ₹16,000
        # 4. Rule 42 does not match Rule 142
        chunks_with_noise = [
            {
                "text": "Section 116 is a different rule. Let's talk about the year 2016. The value is ₹16,000. Under Rule 142, penalties are computed.",
                "metadata": {
                    "rel_path": "noisy_file.pdf",
                    "document_type": "PRIMARY_LAW",
                    "citations": [],
                    "provisions": [],
                    "year": 2017
                }
            }
        ]
        
        # Test Section 16(2)
        res = validate_answer_integrity("Section 16(2) requires invoice.", chunks_with_noise)
        self.assertEqual(res["citations_status"].get("16(2)"), "UNVERIFIED")
        
        # Test Rule 42
        res = validate_answer_integrity("Rule 42 governs reversals.", chunks_with_noise)
        self.assertEqual(res["citations_status"].get("42"), "UNVERIFIED")
        
        # 5. Circular No. 105/2019 is extracted
        # 6. Notification 217/11/2024-GST is extracted correctly
        chunks_with_valid_citations = [
            {
                "text": "Circular No. 105/2019 clarifies post-sale discount treatment under GST.",
                "metadata": {
                    "rel_path": "circular_105.pdf",
                    "document_type": "CIRCULAR",
                    "citations": [],
                    "provisions": [],
                    "year": 2019
                }
            },
            {
                "text": "Notification 217/11/2024-GST defines exemptions.",
                "metadata": {
                    "rel_path": "notification_217.pdf",
                    "document_type": "NOTIFICATION",
                    "citations": [],
                    "provisions": [],
                    "year": 2024
                }
            }
        ]
        
        res = validate_answer_integrity("As per Circular No. 105/2019 and Notification 217/11/2024-GST, the exemption applies.", chunks_with_valid_citations)
        self.assertEqual(res["citations_status"].get("105/2019"), "PARTIAL")
        self.assertEqual(res["citations_status"].get("217/11/2024-GST"), "PARTIAL")
        
        # 7. 18% does not match 118%
        # 8. 30 does not match 130
        # 9. ₹20,00,000 does not match another amount
        chunks_with_noisy_numbers = [
            {
                "text": "The rate is 118%. The period is 130 days. The amount is ₹20,00,005.",
                "metadata": {
                    "rel_path": "noisy_numbers.pdf",
                    "document_type": "PRIMARY_LAW",
                    "citations": [],
                    "provisions": [],
                    "year": 2017
                }
            }
        ]
        
        # Test 18% ungrounded
        res = validate_answer_integrity("The tax rate of 18% is applicable.", chunks_with_noisy_numbers)
        self.assertIn("18%", res["ungrounded_numbers"])
        
        # Test 30 ungrounded
        res = validate_answer_integrity("Verify within 30 days.", chunks_with_noisy_numbers)
        self.assertIn("30", res["ungrounded_numbers"])
        
        # Test ₹20,00,000 ungrounded
        res = validate_answer_integrity("Threshold limit is ₹20,00,000.", chunks_with_noisy_numbers)
        self.assertIn("₹20,00,000", res["ungrounded_numbers"])

if __name__ == "__main__":
    unittest.main()
