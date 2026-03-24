from flashrank import Ranker
import inspect

ranker = Ranker()
print(f"Rerank signature: {inspect.signature(ranker.rerank)}")
print(f"Rerank doc: {ranker.rerank.__doc__}")
