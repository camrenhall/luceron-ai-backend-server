"""
Internal DSL models for agent gateway operations
"""

from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field

class WhereClause(BaseModel):
    """WHERE clause condition in DSL"""
    field: str
    op: str  # Filter operator (=, >, <, etc.)
    value: Any

class OrderByClause(BaseModel):
    """ORDER BY clause in DSL"""
    field: str
    dir: Literal["asc", "desc"] = "asc"

class JoinClause(BaseModel):
    """JOIN clause in DSL"""
    target_resource: str
    on: List[Dict[str, str]]  # [{"leftField": "case_id", "rightField": "case_id"}]
    type: Literal["inner"] = "inner"  # MVP supports only inner joins


class ReadOperation(BaseModel):
    """READ operation in internal DSL"""
    op: Literal["READ"] = "READ"
    resource: str
    select: List[str]
    where: Optional[List[WhereClause]] = None
    joins: Optional[List[JoinClause]] = None  # Support for joins
    order_by: Optional[List[OrderByClause]] = None
    limit: int = 100
    offset: int = 0

class UpdateOperation(BaseModel):
    """UPDATE operation in internal DSL"""
    op: Literal["UPDATE"] = "UPDATE"
    resource: str
    where: List[WhereClause]  # Must include PK equality
    update: Dict[str, Any]  # Fields to set (≤ max_update_fields)
    limit: Literal[1] = 1  # Always 1 for safety

class InsertOperation(BaseModel):
    """INSERT operation in internal DSL"""
    op: Literal["INSERT"] = "INSERT"
    resource: str
    values: Dict[str, Any]  # No explicit IDs; DB generates

# Union type for all operations
DSLOperation = Union[ReadOperation, UpdateOperation, InsertOperation]

class DSL(BaseModel):
    """Complete DSL with operation steps"""
    steps: List[DSLOperation] = Field(min_items=1)
    
    def get_primary_operation(self) -> DSLOperation:
        """Get the primary operation (first step)"""
        return self.steps[0]
    
    def is_read_only(self) -> bool:
        """Check if DSL contains only read operations"""
        return all(step.op == "READ" for step in self.steps)
    
    def is_write_operation(self) -> bool:
        """Check if DSL contains any write operations"""
        return any(step.op in ["INSERT", "UPDATE"] for step in self.steps)
    
    def get_resources(self) -> List[str]:
        """Get all resources referenced in the DSL"""
        return list(set(step.resource for step in self.steps))