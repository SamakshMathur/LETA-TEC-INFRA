from flashrank import Ranker
print(f"Ranker attributes: {dir(Ranker)}")
try:
    ranker = Ranker()
    print(f"Instance attributes: {dir(ranker)}")
except Exception as e:
    print(f"Error instantiating Ranker: {e}")
