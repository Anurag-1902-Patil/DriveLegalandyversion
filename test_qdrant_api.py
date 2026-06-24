from qdrant_client import QdrantClient
import inspect

client = QdrantClient(path="data/qdrant_db")
print("Available public methods on QdrantClient:")
methods = [m for m in dir(client) if not m.startswith('_')]
for m in sorted(methods):
    print(f"  - {m}")

print("\n" + "="*60)
print("Checking for search-related methods:")
search_methods = [m for m in dir(client) if 'search' in m.lower()]
if search_methods:
    print(f"Found: {search_methods}")
else:
    print("No methods with 'search' in name")

print("\n" + "="*60)
if hasattr(client, 'search'):
    print("✓ .search() method EXISTS")
    sig = inspect.signature(client.search)
    print(f"  Signature: {sig}")
else:
    print("✗ .search() method DOES NOT EXIST")

# Check collection
print("\n" + "="*60)
print("Checking collection:")
try:
    collection = client.get_collection("drivelegal_chunks")
    print(f"✓ Collection exists with {collection.points_count} points")
except Exception as e:
    print(f"✗ Error: {e}")
