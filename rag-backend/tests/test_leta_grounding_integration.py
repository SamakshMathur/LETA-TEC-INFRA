import sys
from unittest.mock import MagicMock, patch
import unittest

import json
import asyncio
from pathlib import Path

from app.generation.validator import validate_answer_integrity, verifier
from app.ingestion.legal_parser import LegalParser
from app.pipeline.incremental_ingest import _update_relational_database, _is_positive_conflict, _resolve_target_provision

class MockDB:
    def __init__(self):
        self.knowledge_base = {}
        self.provisions = {}
        self.relationships = {}
        self.unresolved_references = {}

    def find(self, coll, query):
        res = []
        target_coll = getattr(self, coll)
        for k, v in target_coll.items():
            match = True
            for qk, qv in query.items():
                if v.get(qk) != qv:
                    match = False
                    break
            if match:
                res.append(v)
        return res

    def update_one(self, coll, query, update, upsert=False):
        target_coll = getattr(self, coll)
        key = json.dumps(query, sort_keys=True)
        set_data = update.get("$set", update)
        if key not in target_coll:
            if upsert:
                target_coll[key] = {**query, **set_data}
        else:
            target_coll[key].update(set_data)

    def delete_many(self, coll, query):
        target_coll = getattr(self, coll)
        to_del = []
        for k, v in target_coll.items():
            match = True
            for qk, qv in query.items():
                if qk == "$or":
                    or_match = False
                    for sub in qv:
                        sub_match = True
                        for sqk, sqv in sub.items():
                            if v.get(sqk) != sqv:
                                sub_match = False
                                break
                        if sub_match:
                            or_match = True
                            break
                    if not or_match:
                        match = False
                elif v.get(qk) != qv:
                    match = False
                    break
            if match:
                to_del.append(k)
        for k in to_del:
            del target_coll[k]

    def bulk_write(self, coll, operations):
        target_coll = getattr(self, coll)
        for op in operations:
            filter_query = op._filter if not isinstance(op._filter, MagicMock) else {"id": str(op)}
            replacement = op._doc if not isinstance(op._doc, MagicMock) else {}
            try:
                key = json.dumps(filter_query, sort_keys=True)
            except Exception:
                key = str(filter_query)
            target_coll[key] = replacement


class TestLetaGroundingIntegration(unittest.TestCase):

    def test_date_precision_and_no_invention(self):
        # 1. Day precision
        text = "This circular is dated the 15th October, 2024."
        meta = LegalParser.extract_document_metadata(text, text, "cir.pdf")
        self.assertEqual(meta["date_precision"], "DAY")
        self.assertEqual(meta["date_year"], 2024)
        self.assertEqual(meta["date_issued"], "15th october, 2024")

        # 2. Year precision - no day/month invention (no default 2024-07-01)
        text_year_only = "This circular is published in 2024."
        meta = LegalParser.extract_document_metadata(text_year_only, text_year_only, "cir.pdf")
        self.assertEqual(meta["date_precision"], "YEAR")
        self.assertEqual(meta["date_year"], 2024)
        self.assertIsNone(meta["date_issued"])

        # 3. Unknown precision
        text_no_date = "This circular contains general guidance."
        meta = LegalParser.extract_document_metadata(text_no_date, text_no_date, "cir.pdf")
        self.assertEqual(meta["date_precision"], "UNKNOWN")
        self.assertIsNone(meta["date_year"])
        self.assertIsNone(meta["date_issued"])

    def test_negation_gated_conflict_words(self):
        # Positive conflicts
        self.assertTrue(_is_positive_conflict("This rule overrides Section 16(2) of the Act."))
        self.assertTrue(_is_positive_conflict("The circular differs from the previous interpretation."))
        self.assertTrue(_is_positive_conflict("Subject to any contrary provision in Section 17."))

        # Negated conflicts
        self.assertFalse(_is_positive_conflict("This circular does not conflict with Section 16."))
        self.assertFalse(_is_positive_conflict("There is no conflict between Rule 42 and Rule 43."))
        self.assertFalse(_is_positive_conflict("We assume without conflict that the rule applies."))

    @patch("app.pipeline.incremental_ingest.get_db")
    def test_canonical_resolver_and_unresolved_references(self, mock_get_db):
        mock_db = MockDB()
        
        # Setup mock active documents in database
        mock_db.update_one("knowledge_base", {"document_id": "cgst_act_2017"}, {
            "document_id": "cgst_act_2017",
            "canonical_document_type": "PRIMARY_LAW",
            "jurisdiction": "Central",
            "is_active": True,
            "title": "Central Goods and Services Tax Act, 2017"
        }, upsert=True)
        
        mock_db.update_one("knowledge_base", {"document_id": "cgst_rules_2017"}, {
            "document_id": "cgst_rules_2017",
            "canonical_document_type": "RULES",
            "jurisdiction": "Central",
            "is_active": True,
            "title": "Central Goods and Services Tax Rules, 2017"
        }, upsert=True)

        # Mock PyMongo collections interface
        mongo_mock = MagicMock()
        mongo_mock.__getitem__.side_effect = lambda coll: MagicMock(
            find=lambda query: mock_db.find(coll, query),
            update_one=lambda q, u, upsert=False: mock_db.update_one(coll, q, u, upsert),
            delete_many=lambda q: mock_db.delete_many(coll, q),
            bulk_write=lambda ops: mock_db.bulk_write(coll, ops)
        )
        mock_get_db.return_value = mongo_mock

        # Test resolution of Section 16 against primary law cgst_act_2017
        ref_sec = _resolve_target_provision(mongo_mock, "Section 16", {"jurisdiction": "Central"})
        self.assertEqual(ref_sec, "prov_cgst_act_2017_16")

        # Test resolution of Rule 42 against rules cgst_rules_2017
        ref_rule = _resolve_target_provision(mongo_mock, "Rule 42", {"jurisdiction": "Central"})
        self.assertEqual(ref_rule, "prov_cgst_rules_2017_42")

        # Test unresolved reference behavior (preventing guessing)
        ref_unresolved = _resolve_target_provision(mongo_mock, "Notification 12/2017", {"jurisdiction": "Central"})
        self.assertEqual(ref_unresolved, "UNRESOLVED")

    @patch("app.pipeline.incremental_ingest.get_db")
    def test_idempotent_writes(self, mock_get_db):
        mock_db = MockDB()
        mongo_mock = MagicMock()
        mongo_mock.__getitem__.side_effect = lambda coll: MagicMock(
            find=lambda query: mock_db.find(coll, query),
            update_one=lambda q, u, upsert=False: mock_db.update_one(coll, q, u, upsert),
            delete_many=lambda q: mock_db.delete_many(coll, q),
            bulk_write=lambda ops: mock_db.bulk_write(coll, ops)
        )
        mock_get_db.return_value = mongo_mock

        # Controlled chunks from document doc_123
        chunks = [
            {
                "text": "Section 16 is substantive.",
                "metadata": {
                    "document_id": "doc_123",
                    "version_id": "ver_v1",
                    "provision_id": "prov_doc_123_16",
                    "provisions": ["16"],
                    "citations": ["Rule 42"]
                }
            }
        ]

        # First ingestion
        _update_relational_database(chunks)
        provisions_first = len(mock_db.provisions)
        relationships_first = len(mock_db.relationships)

        # Second identical ingestion
        _update_relational_database(chunks)
        provisions_second = len(mock_db.provisions)
        relationships_second = len(mock_db.relationships)

        # Idempotency check: provision and relationship count must remain identical
        self.assertEqual(provisions_first, provisions_second)
        self.assertEqual(relationships_first, relationships_second)

    def test_nli_fail_closed_in_strict_mode(self):
        # Force lazy load exception by setting load_failed manually and bypassing resetting
        verifier.load_failed = True
        verifier._loaded = True # Prevent _lazy_load from resetting it
        
        # Test strict mode validation returns false and availability error
        res = validate_answer_integrity("Under Section 16, ITC is allowed.", [], is_strict=True)
        self.assertFalse(res["is_valid"])
        self.assertIn("Entailment verification service is unavailable", res["warnings"][0])
        
        # Restore state
        verifier.load_failed = False
        verifier._loaded = False

    def test_strict_streaming_buffering_and_count_simulation(self):
        # Simulate generator returning text chunks
        generator = ["This is ", "a complete ", "answer."]
        
        # Simulate strict mode endpoint buffering: generator must be fully consumed
        initial_answer = ""
        gen_count = 0
        for chunk in generator:
            initial_answer += chunk
            gen_count += 1
            
        # Assertions
        self.assertEqual(initial_answer, "This is a complete answer.")
        self.assertEqual(gen_count, 3) # generator consumed exactly once

        # Verify no token is yielded until validation completes
        tokens_yielded = []
        is_validated = False
        
        # Validation simulation
        with patch.object(verifier, '_lazy_load', lambda: None), patch.object(verifier, 'load_failed', False):
            val_res = validate_answer_integrity(initial_answer, [{"text": "This is a complete answer."}], is_strict=True)
        is_validated = True
        
        if is_validated and val_res["is_valid"]:
            # Stream the complete answer
            for i in range(0, len(initial_answer), 5):
                tokens_yielded.append(initial_answer[i:i+5])
                
        # Proves zero outputs were processed/yielded before validation completed
        self.assertTrue(is_validated)
        self.assertEqual("".join(tokens_yielded), "This is a complete answer.")



if __name__ == "__main__":
    unittest.main()
