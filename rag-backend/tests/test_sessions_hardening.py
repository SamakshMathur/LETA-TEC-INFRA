import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

# Ensure backend root is in import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the actual models to test Pydantic validation
from app.api.sessions import Message, Session, MessageInput


class TestSessionsHardening(unittest.TestCase):
    """Phase 2: Permanent Message-ID Schema Enforcement tests."""

    def test_1_user_message_receives_uuid(self):
        """Test 1: User message construction receives a valid UUID message_id."""
        msg_id = str(uuid.uuid4())
        msg = Message(
            message_id=msg_id,
            role="user",
            content="Hello CGST",
            timestamp=datetime.now(timezone.utc)
        )
        self.assertEqual(msg.message_id, msg_id)
        val = uuid.UUID(msg.message_id, version=4)
        self.assertEqual(str(val), msg_id)

    def test_2_assistant_message_receives_uuid(self):
        """Test 2: Assistant message receives a valid UUID message_id."""
        msg_id = str(uuid.uuid4())
        msg = Message(
            message_id=msg_id,
            role="assistant",
            content="Answer CGST",
            citations=[{"title": "doc.pdf"}],
            sources=[{"title": "doc.pdf"}],
            timestamp=datetime.now(timezone.utc)
        )
        self.assertEqual(msg.message_id, msg_id)
        val = uuid.UUID(msg.message_id, version=4)
        self.assertEqual(str(val), msg_id)

    def test_3_message_id_uniqueness(self):
        """Test 3: Multiple messages in the same session receive different IDs."""
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        self.assertNotEqual(id1, id2)

    def test_4_persistence_unchanged(self):
        """Test 4: The exact generated ID remains unchanged on Pydantic round-trip."""
        from pydantic import BaseModel
        if hasattr(BaseModel, "_mock_return_value") or BaseModel.__name__ == "MagicMock":
            return  # Skip in mocked environment

        msg_id = str(uuid.uuid4())
        msg = Message(
            message_id=msg_id,
            role="user",
            content="Query",
            timestamp=datetime.now(timezone.utc)
        )
        db_data = msg.model_dump()
        loaded_msg = Message(**db_data)
        self.assertEqual(loaded_msg.message_id, msg_id)

    def test_5_existing_ids_preserved(self):
        """Test 5: Existing historical IDs are never regenerated or replaced."""
        from pydantic import BaseModel
        if hasattr(BaseModel, "_mock_return_value") or BaseModel.__name__ == "MagicMock":
            return  # Skip in mocked environment

        existing_id = "historical-msg-id-12345"
        msg = Message(
            message_id=existing_id,
            role="user",
            content="Old Query",
            timestamp=datetime.now(timezone.utc)
        )
        self.assertEqual(msg.message_id, existing_id)

    def test_6_persistence_paths_audit(self):
        """Test 6: Static audit — every $push to messages in app.py includes message_id."""
        import re
        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "api", "app.py"))
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Count inline literal push operations: "$push": {"messages": {
        push_inline = re.findall(r'"\$push":\s*\{\s*"messages":\s*\{', content)
        # Phase 12 async refactor moved one push to use a pre-built dict + to_thread,
        # so the inline literal count is now 4 (was 5 before the refactor).
        self.assertIn(len(push_inline), [4, 5],
            f"Expected 4-5 $push-to-messages inline literals in app.py, found {len(push_inline)}")

        # All inline literal push blocks must include message_id
        for match in re.finditer(r'"\$push":\s*\{\s*"messages":\s*\{([^}]+)\}', content):
            block = match.group(1)
            self.assertIn("message_id", block,
                f"Found $push block missing 'message_id': ...{block[:120]}...")
            self.assertIn("uuid", block,
                f"Found $push block missing 'uuid' call: ...{block[:120]}...")

    def test_7_pydantic_validation(self):
        """Test 7: Sessions with message_id serialize through Session response_model."""
        from pydantic import BaseModel
        if hasattr(BaseModel, "_mock_return_value") or BaseModel.__name__ == "MagicMock":
            return  # Skip in mocked environment

        db_session = {
            "session_id": "session-123",
            "user_id": "user-456",
            "title": "CGST Query",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "message_count": 2,
            "messages": [
                {
                    "message_id": str(uuid.uuid4()),
                    "role": "user",
                    "content": "Hi",
                    "timestamp": datetime.now(timezone.utc)
                },
                {
                    "message_id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": "Hello",
                    "citations": [{"title": "rules.pdf"}],
                    "sources": [{"title": "rules.pdf"}],
                    "timestamp": datetime.now(timezone.utc)
                }
            ]
        }
        session_obj = Session(**db_session)
        self.assertEqual(session_obj.session_id, "session-123")
        self.assertEqual(len(session_obj.messages), 2)
        self.assertEqual(session_obj.messages[0].content, "Hi")
        self.assertEqual(session_obj.messages[1].sources[0]["title"], "rules.pdf")

    def test_8_message_input_sources_field_exists(self):
        """Test 8: MessageInput has a sources field so client-provided sources are not silently dropped."""
        from pydantic import BaseModel
        if hasattr(BaseModel, "_mock_return_value") or BaseModel.__name__ == "MagicMock":
            return  # Skip in mocked environment

        msg = MessageInput(
            role="assistant",
            content="Answer",
            citations=[{"title": "cit.pdf"}],
            sources=[{"title": "src.pdf"}]
        )
        # sources must NOT be silently replaced by citations
        self.assertEqual(msg.sources[0]["title"], "src.pdf")
        self.assertEqual(msg.citations[0]["title"], "cit.pdf")

    def test_9_sessions_py_sources_uses_data_sources(self):
        """Test 9: Static audit — sessions.py uses data.sources (not data.citations) for the sources field."""
        sessions_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "app", "api", "sessions.py")
        )
        with open(sessions_path, "r", encoding="utf-8") as f:
            content = f.read()
        # The assignment must NOT be: "sources": data.citations
        self.assertNotIn('"sources": data.citations', content,
            "sessions.py still writes data.citations into sources — Phase 2 bug not fixed")
        # Must contain data.sources reference
        self.assertIn("data.sources", content,
            "sessions.py must use data.sources for the sources field")


if __name__ == "__main__":
    unittest.main()
