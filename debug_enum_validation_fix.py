#!/usr/bin/env python3
"""
Test enum validation fix locally
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_enum_validation():
    """Test that enum validation works in the validator"""
    
    print("🔍 Testing Enum Validation Fix")
    print("=" * 35)
    
    try:
        from agent_gateway.validator import Validator, ValidationError
        from agent_gateway.contracts.cases import get_cases_contract
        from agent_gateway.models.dsl import DSL, ReadOperation, WhereClause
        
        # Create validator
        validator = Validator()
        
        # Create contract
        contract = get_cases_contract()
        contracts = {"cases": contract}
        
        # Test 1: Valid enum value should pass
        print("\n1️⃣ Testing valid enum value 'OPEN'...")
        
        dsl = DSL(steps=[ReadOperation(
            op="READ",
            resource="cases",
            select=["case_id", "status"],
            where=[WhereClause(field="status", op="=", value="OPEN")]
        )])
        
        result = validator.validate(dsl, contracts, "default")
        if result is None:
            print("✅ Valid enum value passed validation")
        else:
            print(f"❌ Valid enum value failed: {result.message}")
            return False
        
        # Test 2: Invalid enum value should fail
        print("\n2️⃣ Testing invalid enum value 'INVALID'...")
        
        dsl_invalid = DSL(steps=[ReadOperation(
            op="READ", 
            resource="cases",
            select=["case_id", "status"],
            where=[WhereClause(field="status", op="=", value="INVALID")]
        )])
        
        result = validator.validate(dsl_invalid, contracts, "default")
        if result and result.error_type == "INVALID_QUERY" and "Valid options are" in result.message:
            print(f"✅ Invalid enum value properly rejected: {result.message}")
        else:
            print(f"❌ Invalid enum value not caught: {result}")
            return False
            
        # Test 3: Another valid value should pass
        print("\n3️⃣ Testing valid enum value 'CLOSED'...")
        
        dsl_closed = DSL(steps=[ReadOperation(
            op="READ",
            resource="cases", 
            select=["case_id", "status"],
            where=[WhereClause(field="status", op="=", value="CLOSED")]
        )])
        
        result = validator.validate(dsl_closed, contracts, "default")
        if result is None:
            print("✅ Valid enum value 'CLOSED' passed validation")
        else:
            print(f"❌ Valid enum value 'CLOSED' failed: {result.message}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    
    print("🚀 Enum Validation Fix Test")
    print("=" * 28)
    
    # Test enum validation
    success = await test_enum_validation()
    
    if success:
        print("\n🎉 SUCCESS: Enum validation fix is working!")
        print("📤 Ready for production deployment")
    else:
        print("\n❌ FAILED: Enum validation fix needs more work")

if __name__ == "__main__":
    asyncio.run(main())