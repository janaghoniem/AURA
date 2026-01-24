"""
Debug script to check Mem0 database state
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI)
db = client["yusr_db"]
collection = db["mem0_preferences"]

print("=" * 70)
print("🔍 MEM0 DATABASE DIAGNOSTIC")
print("=" * 70)

# 1. Count total documents
total_docs = collection.count_documents({})
print(f"\n📊 Total documents in mem0_preferences: {total_docs}")

if total_docs == 0:
    print("❌ DATABASE IS EMPTY - No memories stored!")
    print("\nPossible reasons:")
    print("  1. Preferences are never being added successfully")
    print("  2. Wrong database/collection name")
    print("  3. Mem0 is using a different collection")
    exit()

# 2. Check for test_user data
test_user_docs = collection.count_documents({"payload.user_id": "test_user"})
default_user_docs = collection.count_documents({"payload.user_id": "default_user"})

print(f"\n👤 Documents for test_user: {test_user_docs}")
print(f"👤 Documents for default_user: {default_user_docs}")

# 3. Sample documents
print("\n📄 Sample documents:")
print("-" * 70)

for i, doc in enumerate(collection.find().limit(5), 1):
    print(f"\nDocument {i}:")
    print(f"  ID: {doc.get('_id')}")
    print(f"  User: {doc.get('payload', {}).get('user_id', 'MISSING')}")
    print(f"  Data: {doc.get('data', 'MISSING')}")
    print(f"  Category: {doc.get('payload', {}).get('category', 'MISSING')}")
    
    # Check for embedding
    if 'embedding' in doc:
        print(f"  Embedding: ✅ Present ({len(doc['embedding'])} dims)")
    else:
        print(f"  Embedding: ❌ MISSING")

# 4. Check vector index
print("\n" + "=" * 70)
print("🔍 CHECKING VECTOR SEARCH INDEX")
print("=" * 70)

indexes = list(collection.list_indexes())
print(f"\nFound {len(indexes)} indexes:")

for idx in indexes:
    print(f"\n  • {idx['name']}")
    if 'vectorSearch' in idx.get('type', ''):
        print(f"    Type: Vector Search ✅")
        print(f"    Fields: {idx.get('definition', {})}")

# 5. Test manual search
print("\n" + "=" * 70)
print("🧪 TESTING MANUAL VECTOR SEARCH")
print("=" * 70)

# Try to import mem0 and do a test search
try:
    from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
    
    print("\n📍 Testing with 'default_user'...")
    mgr = get_preference_manager("default_user")
    
    test_queries = [
        "excel",
        "browser",
        "preference",
        "what do I like"
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = mgr.get_relevant_preferences(query, limit=3)
        print(f"  Results: {len(results)}")
        
        for r in results[:2]:
            print(f"    • {r.get('memory', 'No memory field')}")
            
except Exception as e:
    print(f"❌ Test search failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 70)