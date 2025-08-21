"""
Error logs resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits
)

def get_error_logs_contract(role: str = "default") -> ResourceContract:
    """Get error_logs resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="error_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-generated
        ),
        ContractField(
            name="component",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="error_message",
            type=FieldType.TEXT,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="severity",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="context",
            type=FieldType.JSON,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="email_sent",
            type=FieldType.BOOLEAN,
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
        "error_id": [FilterOperator.EQ],
        "component": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "error_message": [FilterOperator.LIKE, FilterOperator.ILIKE],
        "severity": [FilterOperator.EQ, FilterOperator.IN],
        "email_sent": [FilterOperator.EQ],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "updated_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "updated_at", "severity", "component"]
    
    # Operations allowed (READ, INSERT, UPDATE - no DELETE per MVP spec)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    return ResourceContract(
        version="1.0.0",
        resource="error_logs",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=100,
            max_predicates=10,
            max_update_fields=5
        )
    )