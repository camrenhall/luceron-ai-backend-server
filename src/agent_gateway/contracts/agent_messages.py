"""
Agent messages resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits, JoinDefinition
)

def get_agent_messages_contract(role: str = "default") -> ResourceContract:
    """Get agent_messages resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="message_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-generated
        ),
        ContractField(
            name="conversation_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="role",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="content",
            type=FieldType.JSON,
            nullable=False,
            pii=True,  # Message content may contain PII
            readable=True,
            writable=True
        ),
        ContractField(
            name="total_tokens",
            type=FieldType.INTEGER,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="model_used",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="function_name",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="function_arguments",
            type=FieldType.JSON,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="function_response",
            type=FieldType.JSON,
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
            name="sequence_number",
            type=FieldType.INTEGER,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        )
    ]
    
    # Filter operators by field
    filters_allowed = {
        "message_id": [FilterOperator.EQ],
        "conversation_id": [FilterOperator.EQ],
        "role": [FilterOperator.EQ, FilterOperator.IN],
        "total_tokens": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                        FilterOperator.LT, FilterOperator.LTE],
        "model_used": [FilterOperator.EQ, FilterOperator.IN],
        "function_name": [FilterOperator.EQ, FilterOperator.LIKE],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "sequence_number": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                           FilterOperator.LT, FilterOperator.LTE]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "sequence_number", "total_tokens"]
    
    # Operations allowed (READ, INSERT, UPDATE - no DELETE per MVP spec)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    # Allowed JOINs for agent_messages resource
    joins_allowed = [
        JoinDefinition(
            target_resource="agent_conversations",
            on=[{"leftField": "conversation_id", "rightField": "conversation_id"}],
            type="inner"
        )
    ]
    
    return ResourceContract(
        version="1.0.0",
        resource="agent_messages",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=100,
            max_predicates=10,
            max_update_fields=8
        ),
        joins_allowed=joins_allowed
    )