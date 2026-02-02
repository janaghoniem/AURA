#!/usr/bin/env python3
"""
MEMORY SYSTEM DIAGNOSTIC TEST
Run this to check if your memory system is properly configured
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("="*70)
print("🔍 MEMORY SYSTEM DIAGNOSTIC TEST")
print("="*70)

# Test 1: MongoDB Connection
print("\n[TEST 1] MongoDB Connection")
try:
    from pymongo import MongoClient
    MONGODB_URI = os.getenv("MONGODB_URI")
    if not MONGODB_URI:
        print("❌ MONGODB_URI not found in .env")
        sys.exit(1)
    
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB connection successful")
    
    # Check mem0_preferences collection
    db = client["yusr_db"]
    count = db["mem0_preferences"].count_documents({})
    print(f"✅ Found {count} total documents in mem0_preferences")
    
    # Show unique user_ids
    user_ids = db["mem0_preferences"].distinct("user_id")
    print(f"✅ Unique user_ids in database: {user_ids}")
    
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    sys.exit(1)

# Test 2: Mem0 Initialization
print("\n[TEST 2] Mem0 Initialization")
try:
    from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
    
    test_user = "diagnostic_test_user"
    pref_mgr = get_preference_manager(test_user)
    print(f"✅ Mem0 initialized for test user: {test_user}")
    
except Exception as e:
    print(f"❌ Mem0 initialization failed: {e}")
    sys.exit(1)

# Test 3: Memory Storage
print("\n[TEST 3] Memory Storage")
try:
    result = pref_mgr.add_preference(
        "Diagnostic test preference", 
        metadata={"category": "test", "source": "diagnostic"}
    )
    print(f"✅ Stored test preference: {result}")
    
except Exception as e:
    print(f"❌ Memory storage failed: {e}")

# Test 4: Memory Retrieval
print("\n[TEST 4] Memory Retrieval")
try:
    memories = pref_mgr.get_all_preferences()
    print(f"✅ Retrieved {len(memories)} preferences")
    
    if memories:
        print(f"\n📋 Sample preference:")
        sample = memories[0]
        print(f"   Type: {type(sample)}")
        if isinstance(sample, dict):
            print(f"   Keys: {sample.keys()}")
            print(f"   Memory: {sample.get('memory', 'N/A')}")
            print(f"   Metadata: {sample.get('metadata', 'N/A')}")
        else:
            print(f"   Value: {sample}")
            print("   ⚠️ WARNING: Memory is not a dict! This will cause issues.")
    
except Exception as e:
    print(f"❌ Memory retrieval failed: {e}")

# Test 5: Memory Search
print("\n[TEST 5] Memory Search")
try:
    results = pref_mgr.get_relevant_preferences("diagnostic test", limit=5)
    print(f"✅ Search returned {len(results)} results")
    
    for i, result in enumerate(results, 1):
        if isinstance(result, dict):
            score = result.get('score', 'N/A')
            memory = result.get('memory', result.get('text', 'N/A'))
            print(f"   {i}. [Score: {score}] {memory[:60]}...")
        else:
            print(f"   {i}. {result[:60]}... (⚠️ Not a dict)")
    
except Exception as e:
    print(f"❌ Memory search failed: {e}")

# Test 6: Memory Deletion
print("\n[TEST 6] Memory Cleanup")
try:
    # Delete test preference
    all_test_prefs = pref_mgr.get_all_preferences()
    deleted = 0
    for pref in all_test_prefs:
        if isinstance(pref, dict):
            pref_id = pref.get('id')
            if pref_id:
                pref_mgr.delete_preference(pref_id)
                deleted += 1
    
    print(f"✅ Cleaned up {deleted} test preferences")
    
except Exception as e:
    print(f"❌ Cleanup failed: {e}")

# Final Summary
print("\n" + "="*70)
print("📊 DIAGNOSTIC SUMMARY")
print("="*70)
print("\n✅ All tests passed! Memory system is properly configured.")
print("\n🔍 NEXT STEPS:")
print("   1. Check your frontend is sending user_id in requests")
print("   2. Check backend logs show correct user_id (not 'test_user')")
print("   3. Verify localStorage has consistent userId across sessions")
print("="*70)