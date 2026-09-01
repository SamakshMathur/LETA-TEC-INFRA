import unittest
from app.retrieval.scoring_policy import scoring_policy

class TestRetrieval(unittest.TestCase):
    def test_scoring_policy_weights(self):
        self.assertEqual(scoring_policy.weights["semantic"], 0.40)
        self.assertEqual(scoring_policy.weights["authority"], 0.18)

    def test_judicial_intent_boost(self):
        # Case Law with judicial query
        weight = scoring_policy.get_weight("CASE_LAW", "What did the Supreme Court hold in vs Adani?")
        self.assertEqual(weight, 5.0)

    def test_circular_intent_boost(self):
        # Circulars with circular query
        weight = scoring_policy.get_weight("CIRCULAR", "What clarification did CBIC issue in circular?")
        self.assertEqual(weight, 5.0)

if __name__ == "__main__":
    unittest.main()
