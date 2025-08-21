"""
Planner component - converts natural language + contracts to internal DSL
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from agent_gateway.contracts.base import ResourceContract
from agent_gateway.models.dsl import DSL, DSLOperation, ReadOperation, UpdateOperation, InsertOperation
from agent_gateway.utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

@dataclass 
class PlannerResult:
    """Result from planner operation"""
    dsl: DSL
    fingerprint: str  # Stable hash of the DSL for caching/replay

class Planner:
    """Converts natural language + contracts into internal DSL"""
    
    def __init__(self):
        pass
    
    async def plan(
        self,
        natural_language: str,
        contracts: Dict[str, ResourceContract],
        intent: str,
        resources: List[str]
    ) -> PlannerResult:
        """
        Convert natural language + contracts to internal DSL
        
        Args:
            natural_language: The natural language request
            contracts: Resource contracts mapped by resource name
            intent: "READ" or "WRITE" intent from router
            resources: Target resources from router
            
        Returns:
            PlannerResult with DSL and fingerprint
            
        Raises:
            ValueError: If planning fails or produces invalid DSL
            RuntimeError: If LLM call fails
        """
        try:
            # Support READ, INSERT, UPDATE operations
            if intent not in ["READ", "WRITE"]:
                raise ValueError(f"Unsupported intent: {intent}")
            
            # Prepare contract data for LLM (minimal, schema-only)
            contract_data = self._prepare_contracts_for_llm(contracts)
            
            # Use LLM to generate DSL
            llm_client = get_llm_client()
            dsl_dict = await llm_client.plan_operation(
                natural_language=natural_language,
                contracts=contract_data,
                intent=intent,
                resources=resources
            )
            
            # Parse and validate DSL
            dsl = self._parse_and_validate_dsl(dsl_dict, contracts)
            
            # Generate fingerprint for debugging/replay
            fingerprint = self._generate_fingerprint(dsl)
            
            logger.info(f"Planning successful - DSL fingerprint: {fingerprint}")
            
            return PlannerResult(
                dsl=dsl,
                fingerprint=fingerprint
            )
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            raise RuntimeError(f"Planning failed: {str(e)}")
    
    def _prepare_contracts_for_llm(self, contracts: Dict[str, ResourceContract]) -> Dict[str, Any]:
        """Prepare minimal contract data for LLM (no PII, schema only)"""
        
        prepared = {}
        for resource_name, contract in contracts.items():
            prepared[resource_name] = {
                "version": contract.version,
                "resource": contract.resource,
                "ops_allowed": [op.value for op in contract.ops_allowed],
                "fields": [
                    {
                        "name": field.name,
                        "type": field.type.value,
                        "nullable": field.nullable,
                        "readable": field.readable,
                        "writable": field.writable
                    }
                    for field in contract.fields
                    if field.readable  # Only show readable fields
                ],
                "filters_allowed": {
                    field_name: [op.value for op in ops]
                    for field_name, ops in contract.filters_allowed.items()
                },
                "order_allowed": contract.order_allowed,
                "limits": {
                    "max_rows": contract.limits.max_rows,
                    "max_predicates": contract.limits.max_predicates,
                    "max_update_fields": contract.limits.max_update_fields,
                    "max_joins": contract.limits.max_joins
                }
            }
        
        return prepared
    
    def _parse_and_validate_dsl(self, dsl_dict: Dict[str, Any], contracts: Dict[str, ResourceContract]) -> DSL:
        """Parse DSL dictionary and perform basic validation"""
        
        try:
            # Parse using Pydantic models
            dsl = DSL(**dsl_dict)
            
            # Validate each operation
            for step in dsl.steps:
                self._validate_operation(step, contracts)
            
            return dsl
            
        except Exception as e:
            logger.error(f"DSL validation failed: {e}")
            raise ValueError(f"Invalid DSL structure: {str(e)}")
    
    def _validate_operation(self, operation: DSLOperation, contracts: Dict[str, ResourceContract]) -> None:
        """Validate a single DSL operation against contracts"""
        
        # Check resource exists
        if operation.resource not in contracts:
            raise ValueError(f"Unknown resource: {operation.resource}")
        
        contract = contracts[operation.resource]
        
        # Phase 2: Support READ, INSERT, UPDATE operations
        if isinstance(operation, ReadOperation):
            self._validate_read_operation(operation, contract)
        elif isinstance(operation, UpdateOperation):
            self._validate_update_operation(operation, contract)
        elif isinstance(operation, InsertOperation):
            self._validate_insert_operation(operation, contract)
        else:
            raise ValueError(f"Unsupported operation: {operation.op}")
    
    def _validate_read_operation(self, operation: ReadOperation, contract: ResourceContract) -> None:
        """Validate READ operation against contract"""
        
        # Check operation is allowed
        from agent_gateway.contracts.base import Operation
        if Operation.READ not in contract.ops_allowed:
            raise ValueError(f"READ operation not allowed on resource: {operation.resource}")
        
        # Validate selected fields
        for field_name in operation.select:
            if not contract.is_field_readable(field_name):
                raise ValueError(f"Field not readable: {field_name}")
        
        # Validate WHERE clause
        if operation.where:
            if len(operation.where) > contract.limits.max_predicates:
                raise ValueError(f"Too many predicates: {len(operation.where)} > {contract.limits.max_predicates}")
            
            for where_clause in operation.where:
                # Check field exists and is readable
                if not contract.is_field_readable(where_clause.field):
                    raise ValueError(f"WHERE field not readable: {where_clause.field}")
                
                # Check operator is allowed
                from agent_gateway.contracts.base import FilterOperator
                allowed_ops = contract.get_allowed_operators(where_clause.field)
                try:
                    op_enum = FilterOperator(where_clause.op)
                    if op_enum not in allowed_ops:
                        raise ValueError(f"Operator {where_clause.op} not allowed for field {where_clause.field}")
                except ValueError:
                    raise ValueError(f"Invalid operator: {where_clause.op}")
        
        # Validate ORDER BY clause
        if operation.order_by:
            for order_clause in operation.order_by:
                if order_clause.field not in contract.order_allowed:
                    raise ValueError(f"Field not allowed in ORDER BY: {order_clause.field}")
        
        # Validate limits
        if operation.limit > contract.limits.max_rows:
            raise ValueError(f"Limit too high: {operation.limit} > {contract.limits.max_rows}")
        
        if operation.offset < 0:
            raise ValueError(f"Offset cannot be negative: {operation.offset}")
    
    def _validate_update_operation(self, operation: UpdateOperation, contract: ResourceContract) -> None:
        """Validate UPDATE operation against contract"""
        from agent_gateway.contracts.base import Operation
        
        # Check operation is allowed
        if Operation.UPDATE not in contract.ops_allowed:
            raise ValueError(f"UPDATE operation not allowed on resource: {operation.resource}")
        
        # Validate WHERE clause (must include PK equality)
        if not operation.where:
            raise ValueError("UPDATE requires WHERE clause")
        
        # Check for PK equality requirement
        pk_field = self._find_primary_key_field(contract)
        has_pk_equality = False
        for where_clause in operation.where:
            if where_clause.field == pk_field and where_clause.op == "=":
                has_pk_equality = True
                break
        
        if not has_pk_equality:
            raise ValueError(f"UPDATE requires primary key ({pk_field}) equality in WHERE clause")
        
        # Validate limit is exactly 1
        if operation.limit != 1:
            raise ValueError("UPDATE limit must be exactly 1")
        
        # Validate update fields
        if len(operation.update) > contract.limits.max_update_fields:
            raise ValueError(f"Too many update fields: {len(operation.update)} > {contract.limits.max_update_fields}")
        
        for field_name in operation.update.keys():
            if not contract.is_field_writable(field_name):
                raise ValueError(f"Field not writable: {field_name}")
    
    def _validate_insert_operation(self, operation: InsertOperation, contract: ResourceContract) -> None:
        """Validate INSERT operation against contract"""
        from agent_gateway.contracts.base import Operation
        
        # Check operation is allowed
        if Operation.INSERT not in contract.ops_allowed:
            raise ValueError(f"INSERT operation not allowed on resource: {operation.resource}")
        
        # Check that no explicit ID fields are included (DB generates them)
        pk_field = self._find_primary_key_field(contract)
        if pk_field and pk_field in operation.values:
            raise ValueError(f"Cannot specify primary key field {pk_field} in INSERT (auto-generated)")
        
        # Validate all fields exist and are writable
        for field_name in operation.values.keys():
            if not contract.is_field_writable(field_name):
                raise ValueError(f"Field not writable: {field_name}")
    
    def _find_primary_key_field(self, contract: ResourceContract) -> str:
        """Find the primary key field for a resource"""
        # This is a simplified implementation - in practice, you might want to 
        # store PK information in the contract or infer from field names
        common_pk_names = ['id', f'{contract.resource}_id', 'case_id', 'communication_id']
        
        for field in contract.fields:
            if field.name in common_pk_names:
                return field.name
        
        # Fallback to 'id'
        return 'id'

    def _generate_fingerprint(self, dsl: DSL) -> str:
        """Generate stable hash of DSL for caching/replay"""
        import hashlib
        import json
        
        # Convert DSL to dictionary and create stable JSON
        dsl_dict = dsl.dict()
        stable_json = json.dumps(dsl_dict, sort_keys=True, separators=(',', ':'))
        
        # Generate SHA256 hash
        return hashlib.sha256(stable_json.encode()).hexdigest()[:16]  # First 16 chars

# Global planner instance
_planner: Optional[Planner] = None

def get_planner() -> Planner:
    """Get the global planner instance"""
    global _planner
    if _planner is None:
        _planner = Planner()
    return _planner