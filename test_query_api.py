from qdrant_client import QdrantClient
import inspect

client = QdrantClient(path="data/qdrant_db")

# Check query method signature
if hasattr(client, 'query'):
    print("query() method signature:")
    sig = inspect.signature(client.query)
    print(f"  {sig}")
    print(f"\n  Parameters: {list(sig.parameters.keys())}")
else:
    print("No query() method")
