"""
Client communications resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits, JoinDefinition
)

def get_client_communications_contract(role: str = "default") -> ResourceContract:
    """Get client_communications resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="communication_id",
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
            name="channel",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="direction",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="status",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="sender",
            type=FieldType.STRING,
            nullable=False,
            pii=True,
            readable=True,
            writable=True
        ),
        ContractField(
            name="recipient",
            type=FieldType.STRING,
            nullable=False,
            pii=True,
            readable=True,
            writable=True
        ),
        ContractField(
            name="subject",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="message_content",
            type=FieldType.TEXT,
            nullable=True,
            pii=True,
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
            name="sent_at",
            type=FieldType.TIMESTAMP,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="opened_at",
            type=FieldType.TIMESTAMP,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="resend_id",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        )
    ]
    
    # Filter operators by field
    filters_allowed = {
        "communication_id": [FilterOperator.EQ],
        "case_id": [FilterOperator.EQ, FilterOperator.IN],
        "channel": [FilterOperator.EQ, FilterOperator.IN],
        "direction": [FilterOperator.EQ, FilterOperator.IN],
        "status": [FilterOperator.EQ, FilterOperator.IN],
        "sender": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "recipient": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "subject": [FilterOperator.LIKE, FilterOperator.ILIKE],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "sent_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                   FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "sent_at", "channel", "direction", "status"]
    
    
    # Role-specific permissions (Phase 2: READ, INSERT, UPDATE)  
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    # Allowed JOINs for client_communications resource
    joins_allowed = [
        JoinDefinition(
            target_resource="cases",
            on=[{"leftField": "case_id", "rightField": "case_id"}],
            type="inner"
        )
    ]
    
    return ResourceContract(
        version="1.0.0",
        resource="client_communications",
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