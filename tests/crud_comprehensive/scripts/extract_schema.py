#!/usr/bin/env python3
"""
Manual Schema Extraction Script
For debugging and manual schema inspection
"""

import asyncio
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schema_extractor import SchemaExtractor


async def extract_and_save_schema(output_file: str = None, format: str = "json"):
    """Extract schema and save to file"""
    print("🔍 Extracting production database schema...")
    
    try:
        extractor = SchemaExtractor()
        schema = await extractor.extract_full_schema()
        
        # Prepare output
        if format == "json":
            output_data = {
                "extracted_at": schema.extracted_at,
                "schema_hash": schema.schema_hash,
                "version": schema.version,
                "tables": {
                    name: {
                        "table_name": table.table_name,
                        "columns": table.columns,
                        "constraints": table.constraints,
                        "indexes": table.indexes,
                        "foreign_keys": table.foreign_keys,
                        "triggers": table.triggers
                    }
                    for name, table in schema.tables.items()
                }
            }
            
            output_content = json.dumps(output_data, indent=2, default=str)
            
        elif format == "ddl":
            # Generate DDL statements
            ddl_statements = extractor.generate_ddl_statements(schema)
            output_content = "\n".join([
                f"-- Schema extracted at: {schema.extracted_at}",
                f"-- Schema hash: {schema.schema_hash}",
                f"-- Tables: {len(schema.tables)}",
                "",
                *ddl_statements
            ])
        
        # Output to file or stdout
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(output_content)
            
            print(f"✅ Schema saved to: {output_path}")
            print(f"   Hash: {schema.schema_hash}")
            print(f"   Tables: {len(schema.tables)}")
            
        else:
            print("\n" + "="*60)
            print("EXTRACTED SCHEMA")
            print("="*60)
            print(output_content)
        
        return schema
        
    except Exception as e:
        print(f"❌ Schema extraction failed: {e}")
        return None


async def compare_schemas(schema_file1: str, schema_file2: str):
    """Compare two schema files"""
    print(f"🔍 Comparing schemas...")
    print(f"   File 1: {schema_file1}")
    print(f"   File 2: {schema_file2}")
    
    try:
        # Load schemas
        with open(schema_file1, 'r') as f:
            schema1_data = json.load(f)
        
        with open(schema_file2, 'r') as f:
            schema2_data = json.load(f)
        
        # Compare hashes
        hash1 = schema1_data.get("schema_hash", "unknown")
        hash2 = schema2_data.get("schema_hash", "unknown")
        
        print(f"\n📊 Comparison Results:")
        print(f"   Schema 1 hash: {hash1}")
        print(f"   Schema 2 hash: {hash2}")
        
        if hash1 == hash2:
            print(f"   ✅ Schemas are identical")
        else:
            print(f"   ❌ Schemas are different")
            
            # Compare table counts
            tables1 = schema1_data.get("tables", {})
            tables2 = schema2_data.get("tables", {})
            
            print(f"   Tables in schema 1: {len(tables1)}")
            print(f"   Tables in schema 2: {len(tables2)}")
            
            # Find differences
            all_tables = set(tables1.keys()) | set(tables2.keys())
            
            for table_name in sorted(all_tables):
                if table_name not in tables1:
                    print(f"     - {table_name}: Missing in schema 1")
                elif table_name not in tables2:
                    print(f"     + {table_name}: Missing in schema 2")
                else:
                    # Compare column counts
                    cols1 = len(tables1[table_name].get("columns", []))
                    cols2 = len(tables2[table_name].get("columns", []))
                    
                    if cols1 != cols2:
                        print(f"     ~ {table_name}: Column count differs ({cols2} → {cols1})")
        
    except Exception as e:
        print(f"❌ Schema comparison failed: {e}")


async def generate_test_ddl():
    """Generate DDL for creating test database"""
    print("🏗️  Generating test database DDL...")
    
    try:
        extractor = SchemaExtractor()
        schema = await extractor.extract_full_schema()
        
        ddl_statements = extractor.generate_ddl_statements(schema)
        
        print(f"\n📋 Generated {len(ddl_statements)} DDL statements:")
        print("="*60)
        
        for i, statement in enumerate(ddl_statements, 1):
            print(f"-- Statement {i}")
            print(statement)
            print()
        
        # Save to file
        output_file = Path(__file__).parent.parent / "schema_test.sql"
        with open(output_file, 'w') as f:
            f.write(f"-- Test Database Schema\n")
            f.write(f"-- Generated at: {datetime.now().isoformat()}\n")
            f.write(f"-- Schema hash: {schema.schema_hash}\n\n")
            f.write("\n".join(ddl_statements))
        
        print(f"✅ DDL saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ DDL generation failed: {e}")


def create_argument_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Manual Schema Extraction Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/extract_schema.py                        # Extract to stdout (JSON)
  python scripts/extract_schema.py -o schema.json         # Save to file (JSON)
  python scripts/extract_schema.py -o schema.sql --ddl    # Save as DDL
  python scripts/extract_schema.py --generate-ddl         # Generate test DDL
  python scripts/extract_schema.py --compare schema1.json schema2.json
        """
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output file path"
    )
    
    parser.add_argument(
        "--format",
        choices=["json", "ddl"],
        default="json",
        help="Output format (default: json)"
    )
    
    parser.add_argument(
        "--ddl",
        action="store_const",
        const="ddl",
        dest="format",
        help="Output as DDL statements (same as --format ddl)"
    )
    
    parser.add_argument(
        "--generate-ddl", 
        action="store_true",
        help="Generate DDL for test database creation"
    )
    
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Compare two schema files"
    )
    
    return parser


async def main():
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    if args.compare:
        await compare_schemas(args.compare[0], args.compare[1])
    elif args.generate_ddl:
        await generate_test_ddl()
    else:
        await extract_and_save_schema(args.output, args.format)


if __name__ == "__main__":
    asyncio.run(main())