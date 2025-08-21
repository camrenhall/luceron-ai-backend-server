"""
Agent context resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits, JoinDefinition
)

def get_agent_context_contract(role: str = "default") -> ResourceContract:
    """Get agent_context resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="context_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-generated
        ),
        ContractField(
            name="case_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="agent_type",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="context_key",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="context_value",
            type=FieldType.JSON,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="expires_at",
            type=FieldType.TIMESTAMP,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="created_at",
            type=FieldType.TIMESTAMP,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-managed
        ),
        ContractField(
            name="updated_at",
            type=FieldType.TIMESTAMP,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-managed
        )
    ]
    
    # Filter operators by field
    filters_allowed = {
        "context_id": [FilterOperator.EQ],
        "case_id": [FilterOperator.EQ],
        "agent_type": [FilterOperator.EQ, FilterOperator.IN],
        "context_key": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "expires_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "updated_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "updated_at", "context_key", "expires_at"]
    
    # Operations allowed (READ, INSERT, UPDATE - no DELETE per MVP spec)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    # Allowed JOINs for agent_context resource
    joins_allowed = [
        JoinDefinition(
            target_resource="cases",
            on=[{"leftField": "case_id", "rightField": "case_id"}],
            type="inner"
        )
    ]
    
    return ResourceContract(
        version="1.0.0",
        resource="agent_context",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=100,
            max_predicates=10,
            max_update_fields=6
        ),
        joins_allowed=joins_allowed
    )