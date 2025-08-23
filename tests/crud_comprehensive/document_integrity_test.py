#!/usr/bin/env python3
"""
Document Processing Integrity Investigation
Comprehensive test to identify phantom success response root causes
"""

import os
import asyncio
import asyncpg
import sys
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Set environment variables FIRST
DATABASE_URL = 'postgresql://postgres.bjooglksafuxdeknpaso:SgUHEBQv5vdWG0pF@aws-0-us-east-2.pooler.supabase.com:6543/postgres'
os.environ.setdefault("DATABASE_URL", DATABASE_URL)
os.environ.setdefault("RESEND_API_KEY", "dummy_key")

# Add source directory to Python path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from services.documents_service import DocumentsService, DocumentAnalysisService
from services.base_service import ServiceResult
from database.connection import get_db_pool, init_database

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = 'postgresql://postgres.bjooglksafuxdeknpaso:SgUHEBQv5vdWG0pF@aws-0-us-east-2.pooler.supabase.com:6543/postgres'

class DocumentIntegrityTester:
    """Test document processing transaction integrity"""
    
    def __init__(self):
        self.docs_service = DocumentsService()
        self.analysis_service = DocumentAnalysisService()
        self.test_data = []
        self.failed_operations = []
        
    async def setup(self):
        """Initialize database connection"""
        await init_database()
        logger.info("✅ Database connection initialized")
    
    async def teardown(self):
        """Clean up test data"""
        if self.test_data:
            logger.info(f"🧹 Cleaning up {len(self.test_data)} test records")
            for doc_id in self.test_data:
                try:
                    await self.docs_service.delete(doc_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup {doc_id}: {e}")
    
    async def test_basic_create_read_consistency(self) -> Dict[str, Any]:
        """Test 1: Basic CREATE → READ consistency"""
        logger.info("\n1️⃣ Testing Basic CREATE → READ Consistency")
        
        results = {
            "test_name": "basic_create_read_consistency",
            "total_attempts": 0,
            "successful_creates": 0,
            "successful_reads": 0,
            "phantom_successes": 0,
            "timing_issues": [],
            "errors": []
        }
        
        test_cases = [
            {
                "case_id": "123e4567-e89b-12d3-a456-426614174000",
                "original_s3_key": "test_documents/integrity_test_1.pdf",
                "original_s3_location": "s3://test-bucket/test_documents/integrity_test_1.pdf",
                "original_file_name": "integrity_test_1.pdf",
                "original_file_type": "application/pdf",
                "original_file_size": 12345,
                "status": "PENDING"
            },
            {
                "case_id": "123e4567-e89b-12d3-a456-426614174001", 
                "original_s3_key": "test_documents/integrity_test_2.pdf",
                "original_s3_location": "s3://test-bucket/test_documents/integrity_test_2.pdf",
                "original_file_name": "integrity_test_2.pdf",
                "original_file_type": "application/pdf",
                "original_file_size": 67890,
                "status": "PENDING"
            }
        ]
        
        for i, test_data in enumerate(test_cases):
            results["total_attempts"] += 1
            logger.info(f"   Testing document {i+1}...")
            
            try:
                # Measure CREATE timing
                create_start = time.time()
                create_result = await self.docs_service.create(test_data)
                create_duration = time.time() - create_start
                
                if create_result.success and create_result.data:
                    results["successful_creates"] += 1
                    doc_id = create_result.data[0]['document_id']
                    self.test_data.append(doc_id)
                    
                    logger.info(f"   ✅ CREATE successful: {doc_id} ({create_duration:.3f}s)")
                    
                    # Immediate READ test
                    read_start = time.time()
                    read_result = await self.docs_service.get_by_id(doc_id)
                    read_duration = time.time() - read_start
                    
                    if read_result.success and read_result.data:
                        results["successful_reads"] += 1
                        logger.info(f"   ✅ Immediate READ successful ({read_duration:.3f}s)")
                        
                        # Delayed READ test (check for timing issues)
                        await asyncio.sleep(0.1)  # 100ms delay
                        delayed_read = await self.docs_service.get_by_id(doc_id)
                        
                        if not delayed_read.success:
                            results["timing_issues"].append({
                                "doc_id": doc_id,
                                "immediate_read": "success",
                                "delayed_read": "failed",
                                "error": delayed_read.error
                            })
                            logger.warning(f"   ⚠️ Delayed READ failed: {delayed_read.error}")
                            
                    else:
                        # PHANTOM SUCCESS DETECTED
                        results["phantom_successes"] += 1
                        phantom_info = {
                            "doc_id": doc_id,
                            "create_success": True,
                            "read_success": False,
                            "read_error": read_result.error,
                            "create_duration": create_duration,
                            "read_duration": read_duration
                        }
                        self.failed_operations.append(phantom_info)
                        logger.error(f"   ❌ PHANTOM SUCCESS: CREATE claimed success but READ failed")
                        logger.error(f"       Doc ID: {doc_id}")
                        logger.error(f"       Read Error: {read_result.error}")
                        
                else:
                    results["errors"].append({
                        "test_case": i,
                        "error": create_result.error,
                        "error_type": create_result.error_type
                    })
                    logger.error(f"   ❌ CREATE failed: {create_result.error}")
                    
            except Exception as e:
                results["errors"].append({
                    "test_case": i,
                    "exception": str(e)
                })
                logger.error(f"   ❌ Exception during test {i}: {e}")
        
        # Calculate success rates
        if results["total_attempts"] > 0:
            results["create_success_rate"] = results["successful_creates"] / results["total_attempts"]
            results["read_success_rate"] = results["successful_reads"] / results["successful_creates"] if results["successful_creates"] > 0 else 0
            results["phantom_rate"] = results["phantom_successes"] / results["successful_creates"] if results["successful_creates"] > 0 else 0
        
        logger.info(f"\n📊 Basic Consistency Results:")
        logger.info(f"   Create Success Rate: {results.get('create_success_rate', 0):.1%}")
        logger.info(f"   Read Success Rate: {results.get('read_success_rate', 0):.1%}")
        logger.info(f"   Phantom Success Rate: {results.get('phantom_rate', 0):.1%}")
        
        return results
    
    async def test_concurrent_operations(self) -> Dict[str, Any]:
        """Test 2: Concurrent CREATE operations"""
        logger.info("\n2️⃣ Testing Concurrent CREATE Operations")
        
        results = {
            "test_name": "concurrent_operations",
            "concurrent_count": 5,
            "total_attempts": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "race_conditions": [],
            "timing_analysis": []
        }
        
        # Generate concurrent test data
        concurrent_data = []
        for i in range(results["concurrent_count"]):
            concurrent_data.append({
                "case_id": f"123e4567-e89b-12d3-a456-42661417400{i}",
                "original_s3_key": f"test_documents/concurrent_test_{i}.pdf",
                "original_s3_location": f"s3://test-bucket/test_documents/concurrent_test_{i}.pdf",
                "original_file_name": f"concurrent_test_{i}.pdf",
                "original_file_type": "application/pdf",
                "original_file_size": 10000 + i * 1000,
                "status": "PENDING"
            })
        
        # Run concurrent CREATE operations
        start_time = time.time()
        tasks = []
        for i, test_data in enumerate(concurrent_data):
            task = self.create_and_verify_document(test_data, f"concurrent_{i}")
            tasks.append(task)
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze results
        for i, result in enumerate(results_list):
            results["total_attempts"] += 1
            
            if isinstance(result, Exception):
                results["failed_operations"] += 1
                logger.error(f"   ❌ Concurrent operation {i} failed: {result}")
            else:
                if result["success"]:
                    results["successful_operations"] += 1
                    self.test_data.append(result["doc_id"])
                else:
                    results["failed_operations"] += 1
                    if result.get("phantom_success"):
                        results["race_conditions"].append(result)
                
                results["timing_analysis"].append({
                    "operation": i,
                    "duration": result.get("duration", 0),
                    "success": result["success"]
                })
        
        # Calculate metrics
        if results["total_attempts"] > 0:
            results["success_rate"] = results["successful_operations"] / results["total_attempts"]
            results["race_condition_rate"] = len(results["race_conditions"]) / results["total_attempts"]
        
        results["total_duration"] = total_time
        results["avg_operation_time"] = total_time / results["concurrent_count"]
        
        logger.info(f"\n📊 Concurrent Operations Results:")
        logger.info(f"   Success Rate: {results.get('success_rate', 0):.1%}")
        logger.info(f"   Race Condition Rate: {results.get('race_condition_rate', 0):.1%}")
        logger.info(f"   Average Operation Time: {results.get('avg_operation_time', 0):.3f}s")
        
        return results
    
    async def create_and_verify_document(self, test_data: Dict[str, Any], label: str) -> Dict[str, Any]:
        """Helper: Create document and verify consistency"""
        try:
            start_time = time.time()
            
            # Create document
            create_result = await self.docs_service.create(test_data)
            
            if create_result.success and create_result.data:
                doc_id = create_result.data[0]['document_id']
                
                # Immediate verification
                read_result = await self.docs_service.get_by_id(doc_id)
                duration = time.time() - start_time
                
                if read_result.success and read_result.data:
                    return {
                        "success": True,
                        "doc_id": doc_id,
                        "duration": duration,
                        "label": label
                    }
                else:
                    # Phantom success detected
                    return {
                        "success": False,
                        "phantom_success": True,
                        "doc_id": doc_id,
                        "duration": duration,
                        "label": label,
                        "read_error": read_result.error
                    }
            else:
                return {
                    "success": False,
                    "create_error": create_result.error,
                    "duration": time.time() - start_time,
                    "label": label
                }
                
        except Exception as e:
            return {
                "success": False,
                "exception": str(e),
                "duration": time.time() - start_time,
                "label": label
            }
    
    async def test_transaction_isolation(self) -> Dict[str, Any]:
        """Test 3: Transaction isolation analysis"""
        logger.info("\n3️⃣ Testing Transaction Isolation")
        
        results = {
            "test_name": "transaction_isolation",
            "isolation_level": None,
            "transaction_tests": [],
            "connection_analysis": {}
        }
        
        db_pool = get_db_pool()
        
        try:
            async with db_pool.acquire() as conn:
                # Check current isolation level
                isolation_level = await conn.fetchval("SHOW transaction_isolation")
                results["isolation_level"] = isolation_level
                logger.info(f"   Current isolation level: {isolation_level}")
                
                # Test 1: Within-transaction consistency
                logger.info("   Testing within-transaction consistency...")
                async with conn.transaction():
                    # Insert document within transaction
                    doc_data = {
                        "case_id": "123e4567-e89b-12d3-a456-426614174099",
                        "original_s3_key": "test_documents/transaction_test.pdf",
                        "original_s3_location": "s3://test-bucket/test_documents/transaction_test.pdf",
                        "original_file_name": "transaction_test.pdf",
                        "original_file_type": "application/pdf",
                        "original_file_size": 99999
                    }
                    
                    # Manual insert to control transaction
                    insert_result = await conn.fetchrow("""
                        INSERT INTO documents (case_id, original_s3_key, original_s3_location, original_file_name, original_file_type, original_file_size, status, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, 'PENDING', NOW())
                        RETURNING document_id
                    """, doc_data["case_id"], doc_data["original_s3_key"], doc_data["original_s3_location"],
                        doc_data["original_file_name"], doc_data["original_file_type"], doc_data["original_file_size"])
                    
                    if insert_result:
                        doc_id = insert_result["document_id"]
                        self.test_data.append(doc_id)
                        
                        # Try to read within same transaction
                        read_result = await conn.fetchrow("""
                            SELECT document_id, status, created_at 
                            FROM documents 
                            WHERE document_id = $1
                        """, doc_id)
                        
                        if read_result:
                            results["transaction_tests"].append({
                                "test": "within_transaction_read",
                                "success": True,
                                "doc_id": doc_id
                            })
                            logger.info(f"   ✅ Within-transaction read successful: {doc_id}")
                        else:
                            results["transaction_tests"].append({
                                "test": "within_transaction_read", 
                                "success": False,
                                "doc_id": doc_id,
                                "error": "Document not found within same transaction"
                            })
                            logger.error(f"   ❌ Within-transaction read failed: {doc_id}")
                    
                # Test 2: Post-commit consistency
                logger.info("   Testing post-commit consistency...")
                if insert_result:
                    read_result = await conn.fetchrow("""
                        SELECT document_id, status, created_at 
                        FROM documents 
                        WHERE document_id = $1
                    """, doc_id)
                    
                    if read_result:
                        results["transaction_tests"].append({
                            "test": "post_commit_read",
                            "success": True,
                            "doc_id": doc_id
                        })
                        logger.info(f"   ✅ Post-commit read successful: {doc_id}")
                    else:
                        results["transaction_tests"].append({
                            "test": "post_commit_read",
                            "success": False, 
                            "doc_id": doc_id,
                            "error": "Document not found after commit"
                        })
                        logger.error(f"   ❌ Post-commit read failed: {doc_id}")
                
                # Analyze connection info
                results["connection_analysis"] = {
                    "backend_pid": await conn.fetchval("SELECT pg_backend_pid()"),
                    "transaction_isolation": await conn.fetchval("SHOW transaction_isolation"),
                    "in_transaction": conn.get_transaction() is not None
                }
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"   ❌ Transaction isolation test failed: {e}")
        
        return results
    
    async def test_database_constraints(self) -> Dict[str, Any]:
        """Test 4: Database constraint validation"""
        logger.info("\n4️⃣ Testing Database Constraints")
        
        results = {
            "test_name": "database_constraints",
            "foreign_key_tests": [],
            "unique_constraint_tests": [],
            "not_null_tests": []
        }
        
        # Test foreign key constraints
        logger.info("   Testing foreign key constraints...")
        
        # Test with invalid case_id
        invalid_case_data = {
            "case_id": "00000000-0000-0000-0000-000000000000",  # Non-existent case
            "original_s3_key": "test_documents/invalid_case_test.pdf",
            "original_s3_location": "s3://test-bucket/test_documents/invalid_case_test.pdf",
            "original_file_name": "invalid_case_test.pdf",
            "original_file_type": "application/pdf",
            "original_file_size": 12345,
            "status": "pending"
        }
        
        try:
            fk_result = await self.docs_service.create(invalid_case_data)
            results["foreign_key_tests"].append({
                "test": "invalid_case_id",
                "expected": "failure",
                "actual": "success" if fk_result.success else "failure",
                "error": fk_result.error if not fk_result.success else None,
                "error_type": fk_result.error_type if not fk_result.success else None
            })
            
            if fk_result.success:
                logger.warning("   ⚠️ Foreign key constraint not enforced!")
                if fk_result.data:
                    self.test_data.append(fk_result.data[0]['document_id'])
            else:
                logger.info(f"   ✅ Foreign key constraint enforced: {fk_result.error}")
                
        except Exception as e:
            results["foreign_key_tests"].append({
                "test": "invalid_case_id",
                "expected": "failure",
                "actual": "exception",
                "error": str(e)
            })
            logger.info(f"   ✅ Foreign key constraint enforced via exception: {e}")
        
        return results
    
    async def generate_report(self, all_results: List[Dict[str, Any]]) -> str:
        """Generate comprehensive integrity report"""
        logger.info("\n📋 Generating Integrity Report...")
        
        report_lines = [
            "# Document Processing Integrity Analysis Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Executive Summary",
            ""
        ]
        
        # Analyze phantom success rate
        phantom_count = 0
        total_creates = 0
        critical_issues = []
        
        for result in all_results:
            if result["test_name"] == "basic_create_read_consistency":
                phantom_count = result.get("phantom_successes", 0)
                total_creates = result.get("successful_creates", 0)
                
                if result.get("phantom_rate", 0) > 0:
                    critical_issues.append(f"**CRITICAL**: {phantom_count} phantom success responses detected")
            
            elif result["test_name"] == "concurrent_operations":
                race_conditions = len(result.get("race_conditions", []))
                if race_conditions > 0:
                    critical_issues.append(f"**HIGH**: {race_conditions} race conditions detected in concurrent operations")
            
            elif result["test_name"] == "transaction_isolation":
                failed_tests = [t for t in result.get("transaction_tests", []) if not t["success"]]
                if failed_tests:
                    critical_issues.append(f"**CRITICAL**: Transaction isolation failures: {len(failed_tests)} tests failed")
        
        if critical_issues:
            report_lines.extend([
                "🚨 **CRITICAL ISSUES DETECTED** 🚨",
                "",
            ])
            report_lines.extend([f"- {issue}" for issue in critical_issues])
        else:
            report_lines.append("✅ No critical integrity issues detected")
        
        report_lines.extend([
            "",
            "## Detailed Test Results",
            ""
        ])
        
        # Add detailed results for each test
        for result in all_results:
            report_lines.extend([
                f"### {result['test_name'].replace('_', ' ').title()}",
                "",
                f"```json",
                json.dumps(result, indent=2, default=str),
                f"```",
                ""
            ])
        
        # Add recommendations
        report_lines.extend([
            "## Recommendations",
            ""
        ])
        
        if phantom_count > 0:
            report_lines.extend([
                "### 1. CRITICAL: Fix Phantom Success Responses",
                "- Implement proper transaction verification in BaseService._execute_insert_sql()",
                "- Add read-after-write consistency checks",
                "- Consider using RETURNING clause with immediate verification",
                ""
            ])
        
        if any("race_conditions" in r and r.get("race_conditions") for r in all_results):
            report_lines.extend([
                "### 2. HIGH: Address Race Conditions", 
                "- Implement proper connection pooling isolation",
                "- Add row-level locking for critical operations",
                "- Review concurrent operation handling",
                ""
            ])
        
        report_lines.extend([
            "### 3. Transaction Consistency Improvements",
            "- Review PostgreSQL isolation level configuration", 
            "- Implement proper error handling for constraint violations",
            "- Add comprehensive transaction monitoring",
            "",
            "---",
            f"Report generated by Document Integrity Tester v1.0"
        ])
        
        return "\n".join(report_lines)

async def main():
    """Run comprehensive document integrity investigation"""
    logger.info("🔍 Starting Document Processing Integrity Investigation")
    logger.info("=" * 80)
    
    tester = DocumentIntegrityTester()
    all_results = []
    
    try:
        await tester.setup()
        
        # Run all tests
        tests = [
            tester.test_basic_create_read_consistency(),
            tester.test_concurrent_operations(), 
            tester.test_transaction_isolation(),
            tester.test_database_constraints()
        ]
        
        for i, test_coro in enumerate(tests, 1):
            logger.info(f"\n⏳ Running test {i}/{len(tests)}...")
            try:
                result = await test_coro
                all_results.append(result)
            except Exception as e:
                logger.error(f"Test {i} failed with exception: {e}")
                all_results.append({
                    "test_name": f"test_{i}_failed",
                    "error": str(e),
                    "success": False
                })
        
        # Generate report
        report = await tester.generate_report(all_results)
        
        # Save report
        report_path = Path(__file__).parent / "DOCUMENT_INTEGRITY_REPORT.md"
        report_path.write_text(report)
        
        logger.info(f"\n📄 Report saved to: {report_path}")
        logger.info("\n" + "=" * 80)
        logger.info("🏁 Document Integrity Investigation Complete")
        
        # Print summary
        phantom_issues = any(r.get("phantom_successes", 0) > 0 for r in all_results)
        race_conditions = any(r.get("race_conditions") for r in all_results if isinstance(r.get("race_conditions"), list))
        transaction_issues = any(not t.get("success", True) for r in all_results for t in r.get("transaction_tests", []))
        
        if phantom_issues or race_conditions or transaction_issues:
            logger.error("❌ CRITICAL INTEGRITY ISSUES DETECTED - Review report for details")
            return False
        else:
            logger.info("✅ Document processing integrity appears healthy")
            return True
            
    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        return False
        
    finally:
        await tester.teardown()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)