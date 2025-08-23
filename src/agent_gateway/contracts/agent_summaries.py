"""
Agent summaries resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits, JoinDefinition
)

def get_agent_summaries_contract(role: str = "default") -> ResourceContract:
    """Get agent_summaries resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="summary_id",
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
            name="last_message_id",
            type=FieldType.UUID,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="summary_content",
            type=FieldType.TEXT,
            nullable=False,
            pii=True,  # Summary content may contain PII
            readable=True,
            writable=True
        ),
        ContractField(
            name="messages_summarized",
            type=FieldType.INTEGER,
            nullable=False,
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
        "summary_id": [FilterOperator.EQ],
        "conversation_id": [FilterOperator.EQ],
        "last_message_id": [FilterOperator.EQ],
        "summary_content": [FilterOperator.LIKE, FilterOperator.ILIKE],
        "messages_summarized": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                               FilterOperator.LT, FilterOperator.LTE],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "updated_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "updated_at", "messages_summarized"]
    
    # Operations allowed (READ, INSERT, UPDATE, DELETE)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE, Operation.DELETE]
    
    # Allowed JOINs for agent_summaries resource
    joins_allowed = [
        JoinDefinition(
            target_resource="agent_conversations",
            on=[{"leftField": "conversation_id", "rightField": "conversation_id"}],
            type="inner"
        ),
        JoinDefinition(
            target_resource="agent_messages",
            on=[{"leftField": "last_message_id", "rightField": "message_id"}],
            type="inner"
        )
    ]
    
    return ResourceContract(
        version="1.0.0",
        resource="agent_summaries",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=100,
            max_predicates=10,
            max_update_fields=5
        ),
        joins_allowed=joins_allowed
    )