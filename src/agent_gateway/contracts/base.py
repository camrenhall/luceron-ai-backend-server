"""
Base contract models for resource operations
"""

from typing import List, Dict, Literal, Optional
from pydantic import BaseModel
from enum import Enum

class FieldType(str, Enum):
    """Supported field types in contracts"""
    UUID = "uuid"
    STRING = "string"
    TEXT = "text"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    JSON = "json"

class FilterOperator(str, Enum):
    """Allowed filter operators"""
    EQ = "="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "IN"
    BETWEEN = "BETWEEN"
    LIKE = "LIKE"
    ILIKE = "ILIKE"

class Operation(str, Enum):
    """Allowed operations"""
    READ = "READ"
    INSERT = "INSERT"
    UPDATE = "UPDATE"

class ContractField(BaseModel):
    """Field definition within a resource contract"""
    name: str
    type: FieldType
    nullable: bool = True
    pii: bool = False
    readable: bool = True
    writable: bool = False


class ContractLimits(BaseModel):
    """Operational limits for a resource"""
    max_rows: int = 100
    max_predicates: int = 10
    max_update_fields: int = 10
    max_joins: int = 1  # MVP supports max 1 join per query

class JoinDefinition(BaseModel):
    """Allowed JOIN definition in contracts"""
    target_resource: str
    on: List[Dict[str, str]]  # [{"leftField": "case_id", "rightField": "case_id"}]
    type: Literal["inner"] = "inner"

class ResourceContract(BaseModel):
    """Complete resource contract for a specific role"""
    version: str
    resource: str
    ops_allowed: List[Operation]
    fields: List[ContractField]
    filters_allowed: Dict[str, List[FilterOperator]]
    order_allowed: List[str]
    limits: ContractLimits = ContractLimits()
    joins_allowed: Optional[List[JoinDefinition]] = None  # Supported JOINs

    def get_field(self, field_name: str) -> Optional[ContractField]:
        """Get field definition by name"""
        return next((f for f in self.fields if f.name == field_name), None)
    
    def is_field_readable(self, field_name: str) -> bool:
        """Check if field is readable"""
        field = self.get_field(field_name)
        return field is not None and field.readable
    
    def is_field_writable(self, field_name: str) -> bool:
        """Check if field is writable"""
        field = self.get_field(field_name)
        return field is not None and field.writable
    
    def is_operation_allowed(self, operation: Operation) -> bool:
        """Check if operation is allowed"""
        return operation in self.ops_allowed
    
    def get_allowed_operators(self, field_name: str) -> List[FilterOperator]:
        """Get allowed filter operators for a field"""
        return self.filters_allowed.get(field_name, [])
    
    def is_join_allowed(self, target_resource: str, join_fields: List[Dict[str, str]]) -> bool:
        """Check if a join to target resource with given fields is allowed"""
        if not self.joins_allowed:
            return False
        
        for join_def in self.joins_allowed:
            if join_def.target_resource == target_resource:
                # Check if join fields match allowed definition
                if join_def.on == join_fields:
                    return True
        return False