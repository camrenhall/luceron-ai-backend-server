#!/usr/bin/env python3
"""
Test enum fix locally to verify it works before production deployment
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_enum_contract():
    """Test that the enum values are properly included in contracts"""
    
    print("🔍 Testing Enum Contract Fix")
    print("=" * 40)
    
    try:
        # Test contract loading with enum values
        from agent_gateway.contracts.cases import get_cases_contract
        
        contract = get_cases_contract()
        
        # Find status field
        status_field = None
        for field in contract.fields:
            if field.name == "status":
                status_field = field
                break
        
        if status_field:
            print(f"✅ Status field found:")
            print(f"   Type: {status_field.type}")
            print(f"   Nullable: {status_field.nullable}")  
            print(f"   Enum values: {status_field.enum_values}")
            
            if status_field.enum_values == ["OPEN", "CLOSED"]:
                print("✅ Enum values correctly set!")
                return True
            else:
                print(f"❌ Expected ['OPEN', 'CLOSED'], got {status_field.enum_values}")
                return False
        else:
            print("❌ Status field not found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing contract: {e}")
        return False

async def test_contract_preparation():
    """Test that enum values are included in LLM contract preparation"""
    
    print("\n🧠 Testing Contract Preparation for LLM")
    print("=" * 45)
    
    try:
        from agent_gateway.planner import Planner
        from agent_gateway.contracts.cases import get_cases_contract
        
        # Create planner and prepare contracts
        planner = Planner()
        contracts = {"cases": get_cases_contract()}
        
        # Use the internal method to prepare contracts
        prepared = planner._prepare_contracts_for_llm(contracts)
        
        # Check if enum values are included
        if "cases" in prepared:
            cases_fields = prepared["cases"]["fields"]
            status_field = None
            
            for field in cases_fields:
                if field["name"] == "status":
                    status_field = field
                    break
            
            if status_field:
                print(f"✅ Status field in LLM contract:")
                print(f"   Name: {status_field['name']}")
                print(f"   Type: {status_field['type']}")
                print(f"   Nullable: {status_field['nullable']}")
                print(f"   Enum values: {status_field.get('enum_values')}")
                
                if status_field.get('enum_values') == ["OPEN", "CLOSED"]:
                    print("✅ Enum values properly passed to LLM!")
                    return True
                else:
                    print(f"❌ Enum values not correct: {status_field.get('enum_values')}")
                    return False
            else:
                print("❌ Status field not found in LLM contract")
                return False
        else:
            print("❌ Cases contract not found in prepared contracts")
            return False
            
    except Exception as e:
        print(f"❌ Error testing contract preparation: {e}")
        return False

async def main():
    """Main test function"""
    
    print("🚀 Enum Fix Verification")
    print("=" * 25)
    
    # Test 1: Contract enum values
    contract_ok = await test_enum_contract()
    
    if contract_ok:
        # Test 2: LLM preparation
        preparation_ok = await test_contract_preparation()
        
        if preparation_ok:
            print("\n🎉 SUCCESS: Enum fix is working locally!")
            print("📤 Ready for production deployment")
        else:
            print("\n❌ Contract preparation failed")
    else:
        print("\n❌ Contract enum values failed")

if __name__ == "__main__":
    asyncio.run(main())