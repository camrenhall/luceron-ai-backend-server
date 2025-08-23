"""
Validator component - deterministic validation of DSL against contracts
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from agent_gateway.contracts.base import ResourceContract, FilterOperator, Operation
from agent_gateway.models.dsl import DSL, DSLOperation, ReadOperation, UpdateOperation, InsertOperation

logger = logging.getLogger(__name__)

@dataclass
class ValidationError:
    """Validation error details"""
    error_type: str  # Error type from spec
    message: str
    field: Optional[str] = None
    resource: Optional[str] = None

class Validator:
    """Deterministic validator for DSL operations"""
    
    def __init__(self):
        pass
    
    def validate(
        self,
        dsl: DSL,
        contracts: Dict[str, ResourceContract],
        role: str = "default"
    ) -> Optional[ValidationError]:
        """
        Validate DSL against contracts and role permissions
        
        Args:
            dsl: The DSL to validate
            contracts: Resource contracts mapped by name
            role: User role for permission checking
            
        Returns:
            ValidationError if validation fails, None if valid
        """
        try:
            # Validate overall DSL structure
            error = self._validate_dsl_structure(dsl)
            if error:
                return error
            
            # Validate each operation step
            for step in dsl.steps:
                error = self._validate_operation(step, contracts, role)
                if error:
                    return error
            
            # Additional cross-operation validations
            error = self._validate_cross_operations(dsl, contracts)
            if error:
                return error
            
            logger.info("DSL validation successful")
            return None
            
        except Exception as e:
            logger.error(f"Validation failed with exception: {e}")
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Validation error: {str(e)}"
            )
    
    def _validate_dsl_structure(self, dsl: DSL) -> Optional[ValidationError]:
        """Validate overall DSL structure"""
        
        if not dsl.steps:
            return ValidationError(
                error_type="INVALID_QUERY",
                message="DSL must contain at least one operation step"
            )
        
        if len(dsl.steps) > 1:
            # Phase 1: Only single-step operations
            return ValidationError(
                error_type="INVALID_QUERY", 
                message="Multi-step operations not supported in Phase 1"
            )
        
        return None
    
    def _validate_operation(
        self,
        operation: DSLOperation,
        contracts: Dict[str, ResourceContract],
        role: str
    ) -> Optional[ValidationError]:
        """Validate a single DSL operation"""
        
        # Check resource exists
        if operation.resource not in contracts:
            return ValidationError(
                error_type="RESOURCE_NOT_FOUND",
                message=f"Resource not found: {operation.resource}",
                resource=operation.resource
            )
        
        contract = contracts[operation.resource]
        
        # Validate operation type
        if operation.op == "READ":
            return self._validate_read_operation(operation, contract, contracts)
        elif operation.op == "UPDATE":
            return self._validate_update_operation(operation, contract)
        elif operation.op == "INSERT":
            return self._validate_insert_operation(operation, contract)
        elif operation.op == "DELETE":
            # Hard policy: DELETE is disallowed
            return ValidationError(
                error_type="INVALID_QUERY",
                message="DELETE operations are not allowed",
                resource=operation.resource
            )
        else:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Unknown operation: {operation.op}",
                resource=operation.resource
            )
    
    def _validate_read_operation(
        self,
        operation: ReadOperation,
        contract: ResourceContract,
        contracts: Dict[str, ResourceContract]
    ) -> Optional[ValidationError]:
        """Validate READ operation"""
        
        # Check operation is allowed
        if Operation.READ not in contract.ops_allowed:
            return ValidationError(
                error_type="UNAUTHORIZED_OPERATION",
                message=f"READ operation not allowed on {operation.resource}",
                resource=operation.resource
            )
        
        # Validate SELECT fields
        for field_name in operation.select:
            field = contract.get_field(field_name)
            if not field:
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"Field does not exist: {field_name}",
                    field=field_name,
                    resource=operation.resource
                )
            
            if not field.readable:
                return ValidationError(
                    error_type="UNAUTHORIZED_FIELD",
                    message=f"Field not readable: {field_name}",
                    field=field_name,
                    resource=operation.resource
                )
        
        # Validate WHERE clauses
        if operation.where:
            error = self._validate_where_clauses(operation.where, contract)
            if error:
                return error
        
        # Validate ORDER BY clauses
        if operation.order_by:
            for order_clause in operation.order_by:
                if order_clause.field not in contract.order_allowed:
                    return ValidationError(
                        error_type="INVALID_QUERY",
                        message=f"Field not allowed in ORDER BY: {order_clause.field}",
                        field=order_clause.field,
                        resource=operation.resource
                    )
        
        # Validate JOIN clauses
        if operation.joins:
            error = self._validate_join_clauses(operation.joins, contract, contracts)
            if error:
                return error
        
        # Validate limits
        if operation.limit > contract.limits.max_rows:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Limit exceeds maximum: {operation.limit} > {contract.limits.max_rows}",
                resource=operation.resource
            )
        
        if operation.limit <= 0:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Limit must be positive: {operation.limit}",
                resource=operation.resource
            )
        
        if hasattr(operation, 'offset') and operation.offset < 0:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Offset cannot be negative: {operation.offset}",
                resource=operation.resource
            )
        
        return None
    
    def _validate_update_operation(
        self,
        operation: UpdateOperation,
        contract: ResourceContract
    ) -> Optional[ValidationError]:
        """Validate UPDATE operation (Phase 2)"""
        
        # Check operation is allowed
        if Operation.UPDATE not in contract.ops_allowed:
            return ValidationError(
                error_type="UNAUTHORIZED_OPERATION",
                message=f"UPDATE operation not allowed on {operation.resource}",
                resource=operation.resource
            )
        
        # Validate limit is exactly 1 (safety constraint)
        if operation.limit != 1:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"UPDATE limit must be exactly 1, got: {operation.limit}",
                resource=operation.resource
            )
        
        # Validate WHERE clause (must include PK equality)
        if not operation.where:
            return ValidationError(
                error_type="INVALID_QUERY",
                message="UPDATE operations must include WHERE clause with primary key",
                resource=operation.resource
            )
        
        # Find primary key field (usually ends with _id and is not writable)
        pk_field = self._find_primary_key_field(contract)
        if not pk_field:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Cannot identify primary key field for {operation.resource}",
                resource=operation.resource
            )
        
        # Ensure PK equality is present in WHERE clause
        pk_equality_found = False
        for where_clause in operation.where:
            if where_clause.field == pk_field and where_clause.op == "=":
                pk_equality_found = True
                break
        
        if not pk_equality_found:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"UPDATE must include primary key equality: {pk_field} = value",
                resource=operation.resource
            )
        
        # Validate WHERE clauses
        error = self._validate_where_clauses(operation.where, contract)
        if error:
            return error
        
        # Validate UPDATE fields
        if len(operation.update) > contract.limits.max_update_fields:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Too many update fields: {len(operation.update)} > {contract.limits.max_update_fields}",
                resource=operation.resource
            )
        
        for field_name, value in operation.update.items():
            field = contract.get_field(field_name)
            if not field:
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"Field does not exist: {field_name}",
                    field=field_name,
                    resource=operation.resource
                )
            
            if not field.writable:
                return ValidationError(
                    error_type="UNAUTHORIZED_FIELD",
                    message=f"Field not writable: {field_name}",
                    field=field_name,
                    resource=operation.resource
                )
            
            # Validate field value type and enum constraints
            error = self._validate_field_value(field_name, field, value, operation.resource)
            if error:
                return error
        
        return None
    
    def _validate_insert_operation(
        self,
        operation: InsertOperation,
        contract: ResourceContract
    ) -> Optional[ValidationError]:
        """Validate INSERT operation (Phase 2)"""
        
        # Check operation is allowed
        if Operation.INSERT not in contract.ops_allowed:
            return ValidationError(
                error_type="UNAUTHORIZED_OPERATION",
                message=f"INSERT operation not allowed on {operation.resource}",
                resource=operation.resource
            )
        
        # Check that no explicit ID fields are included (DB generates them)
        pk_field = self._find_primary_key_field(contract)
        if pk_field and pk_field in operation.values:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Cannot specify primary key field {pk_field} in INSERT (auto-generated)",
                field=pk_field,
                resource=operation.resource
            )
        
        # Validate all fields exist and are writable
        for field_name, value in operation.values.items():
            field = contract.get_field(field_name)
            if not field:
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"Field does not exist: {field_name}",
                    field=field_name,
                    resource=operation.resource
                )
            
            if not field.writable:
                return ValidationError(
                    error_type="UNAUTHORIZED_FIELD",
                    message=f"Field not writable: {field_name}",
                    field=field_name,
                    resource=operation.resource
                )
            
            # Validate field value type and enum constraints
            error = self._validate_field_value(field_name, field, value, operation.resource)
            if error:
                return error
        
        # Check required non-nullable fields are provided
        for field in contract.fields:
            if not field.nullable and field.writable and field.name not in operation.values:
                # Skip auto-managed fields (created_at, etc.)
                if field.name not in ['created_at', 'updated_at'] and field.name != pk_field:
                    return ValidationError(
                        error_type="INVALID_QUERY",
                        message=f"Required field missing: {field.name}",
                        field=field.name,
                        resource=operation.resource
                    )
        
        return None
    
    def _validate_where_clauses(
        self,
        where_clauses: List,
        contract: ResourceContract
    ) -> Optional[ValidationError]:
        """Validate WHERE clause conditions"""
        
        if len(where_clauses) > contract.limits.max_predicates:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Too many predicates: {len(where_clauses)} > {contract.limits.max_predicates}",
                resource=contract.resource
            )
        
        for where_clause in where_clauses:
            field_name = where_clause.field
            operator = where_clause.op
            value = where_clause.value
            
            # Check field exists and is readable
            field = contract.get_field(field_name)
            if not field:
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"Field does not exist: {field_name}",
                    field=field_name,
                    resource=contract.resource
                )
            
            if not field.readable:
                return ValidationError(
                    error_type="UNAUTHORIZED_FIELD",
                    message=f"Field not readable in WHERE clause: {field_name}",
                    field=field_name,
                    resource=contract.resource
                )
            
            # Validate operator is allowed for this field
            try:
                op_enum = FilterOperator(operator)
            except ValueError:
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"Invalid operator: {operator}",
                    field=field_name,
                    resource=contract.resource
                )
            
            allowed_ops = contract.get_allowed_operators(field_name)
            if op_enum not in allowed_ops:
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"Operator {operator} not allowed for field {field_name}",
                    field=field_name,
                    resource=contract.resource
                )
            
            # Basic type validation and enum checking
            error = self._validate_field_value(field_name, field, value, contract.resource)
            if error:
                return error
        
        return None
    
    def _validate_field_value(self, field_name: str, field, value, resource: str) -> Optional[ValidationError]:
        """Validate field value matches expected type and enum constraints"""
        
        # Basic type checking - can be extended
        from agent_gateway.contracts.base import FieldType
        
        if value is None:
            return None  # NULL values handled by nullable flag
        
        # Check enum values first if they exist
        if field.enum_values and value not in field.enum_values:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Invalid value for field {field_name}: '{value}'. Valid options are: {', '.join(field.enum_values)}",
                field=field_name,
                resource=resource
            )
        
        field_type = field.type
        try:
            if field_type == FieldType.UUID:
                import uuid
                if isinstance(value, str):
                    uuid.UUID(value)  # Validate UUID format
            elif field_type == FieldType.INTEGER:
                if not isinstance(value, int):
                    int(value)  # Try conversion
            elif field_type == FieldType.NUMBER:
                if not isinstance(value, (int, float)):
                    float(value)  # Try conversion
            elif field_type == FieldType.BOOLEAN:
                if not isinstance(value, bool):
                    if isinstance(value, str):
                        if value.lower() not in ['true', 'false']:
                            raise ValueError("Invalid boolean value")
            elif field_type in [FieldType.DATE, FieldType.TIMESTAMP]:
                if isinstance(value, str):
                    from datetime import datetime
                    # Basic ISO format check
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError) as e:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Invalid value for {field_type.value} field {field_name}: {value}",
                field=field_name,
                resource=resource
            )
        
        return None
    
    def _validate_join_clauses(
        self,
        join_clauses: List,
        contract: ResourceContract,
        contracts: Dict[str, ResourceContract]
    ) -> Optional[ValidationError]:
        """Validate JOIN clause conditions"""
        
        # Check JOIN limit
        if len(join_clauses) > contract.limits.max_joins:
            return ValidationError(
                error_type="INVALID_QUERY",
                message=f"Too many joins: {len(join_clauses)} > {contract.limits.max_joins}",
                resource=contract.resource
            )
        
        for join_clause in join_clauses:
            target_resource = join_clause.target_resource
            join_on = join_clause.on
            join_type = join_clause.type
            
            # Check target resource exists in contracts
            if target_resource not in contracts:
                return ValidationError(
                    error_type="RESOURCE_NOT_FOUND",
                    message=f"JOIN target resource not found: {target_resource}",
                    resource=contract.resource
                )
            
            # Check JOIN type is supported (MVP: only inner)
            if join_type != "inner":
                return ValidationError(
                    error_type="INVALID_QUERY",
                    message=f"JOIN type not supported: {join_type}. Only 'inner' joins are allowed",
                    resource=contract.resource
                )
            
            # Check if this join is allowed by contract
            if not contract.is_join_allowed(target_resource, join_on):
                return ValidationError(
                    error_type="UNAUTHORIZED_OPERATION",
                    message=f"JOIN to {target_resource} not allowed by contract",
                    resource=contract.resource
                )
            
            # Validate join field existence and accessibility
            target_contract = contracts[target_resource]
            
            for join_spec in join_on:
                # Validate left field (from main resource)
                left_field = join_spec.get("leftField")
                if not left_field:
                    return ValidationError(
                        error_type="INVALID_QUERY",
                        message="JOIN clause missing leftField",
                        resource=contract.resource
                    )
                
                left_field_def = contract.get_field(left_field)
                if not left_field_def:
                    return ValidationError(
                        error_type="INVALID_QUERY",
                        message=f"JOIN left field does not exist: {left_field}",
                        field=left_field,
                        resource=contract.resource
                    )
                
                if not left_field_def.readable:
                    return ValidationError(
                        error_type="UNAUTHORIZED_FIELD",
                        message=f"JOIN left field not readable: {left_field}",
                        field=left_field,
                        resource=contract.resource
                    )
                
                # Validate right field (from target resource)
                right_field = join_spec.get("rightField")
                if not right_field:
                    return ValidationError(
                        error_type="INVALID_QUERY",
                        message="JOIN clause missing rightField",
                        resource=contract.resource
                    )
                
                right_field_def = target_contract.get_field(right_field)
                if not right_field_def:
                    return ValidationError(
                        error_type="INVALID_QUERY",
                        message=f"JOIN right field does not exist: {right_field}",
                        field=right_field,
                        resource=target_resource
                    )
                
                if not right_field_def.readable:
                    return ValidationError(
                        error_type="UNAUTHORIZED_FIELD",
                        message=f"JOIN right field not readable: {right_field}",
                        field=right_field,
                        resource=target_resource
                    )
        
        return None
    
    def _find_primary_key_field(self, contract: ResourceContract) -> Optional[str]:
        """Find the primary key field in a contract (usually ends with _id and not writable)"""
        # Look for fields ending with _id that are not writable (auto-generated)
        for field in contract.fields:
            if field.name.endswith('_id') and not field.writable:
                return field.name
        
        # Fallback: look for common PK names
        common_pk_names = ['id', f"{contract.resource.rstrip('s')}_id"]
        for field in contract.fields:
            if field.name in common_pk_names and not field.writable:
                return field.name
        
        return None
    
    def _validate_cross_operations(self, dsl: DSL, contracts: Dict[str, ResourceContract]) -> Optional[ValidationError]:
        """Validate cross-operation constraints"""
        
        # Phase 1: Single operations only, no cross-validation needed
        return None

# Global validator instance
_validator: Optional[Validator] = None

def get_validator() -> Validator:
    """Get the global validator instance"""
    global _validator
    if _validator is None:
        _validator = Validator()
    return _validator