from qdrant_client import QdrantClient
import inspect

client = QdrantClient(path="data/qdrant_db")

# Check query_points method
if hasattr(client, 'query_points'):
    print("query_points() method signature:")
    sig = inspect.signature(client.query_points)
    print(f"  {sig}")
    print(f"\n  Parameters: {list(sig.parameters.keys())}")
else:
    print("No query_points() method")
