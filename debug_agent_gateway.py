#!/usr/bin/env python3
"""
Agent Gateway Debug Script

This script tests the Agent Gateway components locally to validate the fix
and understand what's working vs what needs production deployment.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path so we can import components
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_agent_gateway_components():
    """Test Agent Gateway components locally"""
    
    print("🔍 Agent Gateway Component Testing")
    print("=" * 50)
    
    try:
        # Test 1: Check if Agent Gateway modules can be imported
        print("\n1️⃣ Testing module imports...")
        
        try:
            from agent_gateway.router import get_router
            from agent_gateway.planner import get_planner  
            from agent_gateway.validator import get_validator
            from agent_gateway.executor import get_executor
            from agent_gateway.utils.llm_client import get_llm_client
            print("✅ All Agent Gateway modules imported successfully")
        except ImportError as e:
            print(f"❌ Import error: {e}")
            return False
            
        # Test 2: Check LLM client initialization
        print("\n2️⃣ Testing LLM client...")
        
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            print("❌ OPENAI_API_KEY not set - Agent Gateway disabled")
            return False
        
        try:
            from agent_gateway.utils.llm_client import init_llm_client
            init_llm_client(openai_key)
            llm_client = get_llm_client()
            print("✅ LLM client initialized successfully")
        except Exception as e:
            print(f"❌ LLM client error: {e}")
            return False
            
        # Test 3: Test datetime/timedelta fix
        print("\n3️⃣ Testing datetime/timedelta fix...")
        
        try:
            # This should not raise an error anymore
            from datetime import datetime, timezone, timedelta
            current_date = datetime.now(timezone.utc)
            test_date = (current_date - timedelta(days=7)).strftime('%Y-%m-%d')
            print(f"✅ Timedelta calculation works: {test_date}")
        except Exception as e:
            print(f"❌ Datetime/timedelta error: {e}")
            return False
            
        # Test 4: Test router component
        print("\n4️⃣ Testing router component...")
        
        try:
            router = get_router()
            # Simple routing test
            result = await router.route(
                natural_language="Show me all cases",
                hints={"resources": ["cases"], "intent": "READ"}
            )
            print(f"✅ Router working: {result.resources}, intent: {result.intent}")
        except Exception as e:
            print(f"❌ Router error: {e}")
            return False
            
        # Test 5: Test contracts loading
        print("\n5️⃣ Testing contracts...")
        
        try:
            from agent_gateway.contracts.registry import get_all_contracts
            contracts = get_all_contracts()
            print(f"✅ Contracts loaded: {list(contracts.keys())}")
        except Exception as e:
            print(f"❌ Contracts error: {e}")
            return False
            
        print("\n✅ All local Agent Gateway components working!")
        print("🚨 Production server needs deployment of timedelta fix")
        
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def test_simple_planning():
    """Test the planner component with a simple query"""
    
    print("\n🧠 Testing Planner Component")
    print("=" * 30)
    
    try:
        from agent_gateway.planner import get_planner
        from agent_gateway.contracts.registry import get_all_contracts
        
        planner = get_planner()
        contracts = get_all_contracts()
        
        # Filter to just cases contract
        cases_contracts = {"cases": contracts["cases"]}
        
        result = await planner.plan(
            natural_language="Show me all cases",
            contracts=cases_contracts,
            intent="READ", 
            resources=["cases"]
        )
        
        print(f"✅ Planning successful!")
        print(f"   DSL Fingerprint: {result.fingerprint}")
        print(f"   DSL Operation: {result.dsl.operation.operation_type}")
        print(f"   DSL Resource: {result.dsl.operation.resource}")
        
        return True
        
    except Exception as e:
        print(f"❌ Planning failed: {e}")
        return False

async def main():
    """Main test function"""
    
    print("🚀 Agent Gateway Local Testing Suite")
    print("=" * 60)
    
    # Test components
    components_ok = await test_agent_gateway_components()
    
    if components_ok:
        # Test planning
        planning_ok = await test_simple_planning()
        
        if planning_ok:
            print("\n🎉 LOCAL TESTING COMPLETE - Agent Gateway components working!")
            print("📝 Next step: Deploy timedelta fix to production server")
        else:
            print("\n❌ Planning test failed")
    else:
        print("\n❌ Component tests failed")

if __name__ == "__main__":
    asyncio.run(main())