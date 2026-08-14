"""
Quick script to test Firestore community_reports collection
"""
import sys
sys.path.append('.')

from app.repositories.firestore_repository import init_firebase, _get_db
from firebase_admin import firestore

init_firebase()
db = _get_db()

print("=" * 60)
print("TESTING FIRESTORE COMMUNITY_REPORTS COLLECTION")
print("=" * 60)

# Test 1: Count all documents
collection_ref = db.collection("community_reports")
all_docs = list(collection_ref.stream())
print(f"\n1. Total documents in community_reports: {len(all_docs)}")

if all_docs:
    print("\n2. Sample documents:")
    for i, doc in enumerate(all_docs[:3]):  # Show first 3
        d = doc.to_dict()
        print(f"\n   Document {i+1} (ID: {doc.id}):")
        print(f"   - reportId: {d.get('reportId')}")
        print(f"   - type: {d.get('type')}")
        print(f"   - content: {d.get('content', '')[:50]}...")
        print(f"   - verifiedStatus: {d.get('verifiedStatus')}")
        print(f"   - createdAt: {d.get('createdAt')}")
        print(f"   - reportedBy: {d.get('reportedBy')}")

# Test 2: Query with order by (like admin endpoint)
print(f"\n3. Testing query with order_by createdAt DESC:")
try:
    query = collection_ref.order_by("createdAt", direction=firestore.Query.DESCENDING)
    query_docs = list(query.limit(10).stream())
    print(f"   ✓ Query successful! Found {len(query_docs)} documents")
    
    if query_docs:
        first = query_docs[0].to_dict()
        print(f"   Latest report:")
        print(f"   - createdAt: {first.get('createdAt')}")
        print(f"   - type: {first.get('type')}")
        print(f"   - status: {first.get('verifiedStatus')}")
except Exception as e:
    print(f"   ✗ Query failed: {e}")

# Test 3: Query with filter (like when status_filter provided)
print(f"\n4. Testing query with verifiedStatus filter:")
try:
    query_filtered = collection_ref.where("verifiedStatus", "==", "pending").order_by("createdAt", direction=firestore.Query.DESCENDING)
    filtered_docs = list(query_filtered.limit(10).stream())
    print(f"   ✓ Filtered query successful! Found {len(filtered_docs)} pending reports")
except Exception as e:
    print(f"   ✗ Filtered query failed: {e}")
    print(f"   This likely means composite index is not ready yet.")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
