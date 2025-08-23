"""
Cases resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits, JoinDefinition
)

def get_cases_contract(role: str = "default") -> ResourceContract:
    """Get cases resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="case_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-generated
        ),
        ContractField(
            name="client_name",
            type=FieldType.STRING,
            nullable=False,
            pii=True,
            readable=True,
            writable=True
        ),
        ContractField(
            name="client_email",
            type=FieldType.STRING,
            nullable=False,
            pii=True,
            readable=True,
            writable=True
        ),
        ContractField(
            name="client_phone",
            type=FieldType.STRING,
            nullable=True,
            pii=True,
            readable=True,
            writable=True
        ),
        ContractField(
            name="status",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True,
            enum_values=["OPEN", "CLOSED"]
        ),
        ContractField(
            name="created_at",
            type=FieldType.TIMESTAMP,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-managed
        )
    ]
    
    # Filter operators by field
    filters_allowed = {
        "case_id": [FilterOperator.EQ],
        "client_name": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "client_email": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "client_phone": [FilterOperator.EQ, FilterOperator.LIKE],
        "status": [FilterOperator.EQ, FilterOperator.IN],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "client_name", "status"]
    
    # Role-specific permissions (Phase 2: READ, INSERT, UPDATE)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    # Allowed JOINs for cases resource
    joins_allowed = [
        JoinDefinition(
            target_resource="client_communications",
            on=[{"leftField": "case_id", "rightField": "case_id"}],
            type="inner"
        )
    ]
    
    return ResourceContract(
        version="1.0.0",
        resource="cases",
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