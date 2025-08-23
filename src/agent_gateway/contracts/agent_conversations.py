"""
Agent conversations resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits
)

def get_agent_conversations_contract(role: str = "default") -> ResourceContract:
    """Get agent_conversations resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="conversation_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-generated
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
            name="status",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="total_tokens_used",
            type=FieldType.INTEGER,
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
        "conversation_id": [FilterOperator.EQ],
        "agent_type": [FilterOperator.EQ, FilterOperator.IN],
        "status": [FilterOperator.EQ, FilterOperator.IN],
        "total_tokens_used": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                             FilterOperator.LT, FilterOperator.LTE],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "updated_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "updated_at", "total_tokens_used", "agent_type"]
    
    # Operations allowed (READ, INSERT, UPDATE, DELETE)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE, Operation.DELETE]
    
    return ResourceContract(
        version="1.0.0",
        resource="agent_conversations",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=100,
            max_predicates=10,
            max_update_fields=4
        )
    )