"""
Documents resource contract definitions
"""

from agent_gateway.contracts.base import (
    ResourceContract, ContractField, FieldType, FilterOperator, 
    Operation, ContractLimits
)

def get_documents_contract(role: str = "default") -> ResourceContract:
    """Get documents resource contract for specified role"""
    
    # Base field definitions
    fields = [
        ContractField(
            name="document_id",
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
            name="original_file_name",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="original_file_size",
            type=FieldType.INTEGER,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="original_file_type",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="original_s3_location",
            type=FieldType.STRING,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="original_s3_key",
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
            name="created_at",
            type=FieldType.TIMESTAMP,
            nullable=False,
            pii=False,
            readable=True,
            writable=False  # Auto-managed
        ),
        ContractField(
            name="processed_file_name",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="processed_file_size",
            type=FieldType.INTEGER,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="processed_s3_location",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="processed_s3_key",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="batch_id",
            type=FieldType.STRING,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        )
    ]
    
    # Filter operators by field
    filters_allowed = {
        "document_id": [FilterOperator.EQ],
        "case_id": [FilterOperator.EQ, FilterOperator.IN],
        "original_file_name": [FilterOperator.EQ, FilterOperator.LIKE, FilterOperator.ILIKE],
        "original_file_type": [FilterOperator.EQ, FilterOperator.IN],
        "status": [FilterOperator.EQ, FilterOperator.IN],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "original_file_size": [FilterOperator.GT, FilterOperator.LTE],
        "batch_id": [FilterOperator.EQ]
    }
    
    # Fields allowed for ordering
    order_allowed = ["created_at", "original_file_name", "status", "original_file_size"]
    
    
    # Role-specific permissions (Phase 2: READ, INSERT, UPDATE)
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    return ResourceContract(
        version="1.0.0",
        resource="documents",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=100,
            max_predicates=10,
            max_update_fields=8
        )
    )

def get_document_analysis_contract(role: str = "default") -> ResourceContract:
    """Get document_analysis resource contract for specified role"""
    
    fields = [
        ContractField(
            name="analysis_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=False
        ),
        ContractField(
            name="document_id",
            type=FieldType.UUID,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
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
            name="analysis_content",
            type=FieldType.TEXT,
            nullable=False,
            pii=True,  # May contain sensitive analysis
            readable=True,
            writable=True
        ),
        ContractField(
            name="analysis_status",
            type=FieldType.STRING,
            nullable=False,
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
            name="tokens_used",
            type=FieldType.INTEGER,
            nullable=True,
            pii=False,
            readable=True,
            writable=True
        ),
        ContractField(
            name="analyzed_at",
            type=FieldType.TIMESTAMP,
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
            writable=False
        ),
        ContractField(
            name="analysis_reasoning",
            type=FieldType.TEXT,
            nullable=True,
            pii=True,
            readable=True,
            writable=True
        ),
        ContractField(
            name="context_summary_created",
            type=FieldType.BOOLEAN,
            nullable=False,
            pii=False,
            readable=True,
            writable=True
        )
    ]
    
    filters_allowed = {
        "analysis_id": [FilterOperator.EQ],
        "document_id": [FilterOperator.EQ, FilterOperator.IN],
        "case_id": [FilterOperator.EQ, FilterOperator.IN],
        "analysis_status": [FilterOperator.EQ, FilterOperator.IN],
        "model_used": [FilterOperator.EQ],
        "analyzed_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                       FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "created_at": [FilterOperator.EQ, FilterOperator.GT, FilterOperator.GTE, 
                      FilterOperator.LT, FilterOperator.LTE, FilterOperator.BETWEEN],
        "context_summary_created": [FilterOperator.EQ]
    }
    
    order_allowed = ["analyzed_at", "created_at", "analysis_status"]
    
    
    ops_allowed = [Operation.READ, Operation.INSERT, Operation.UPDATE]
    
    return ResourceContract(
        version="1.0.0",
        resource="document_analysis",
        ops_allowed=ops_allowed,
        fields=fields,
        filters_allowed=filters_allowed,
        order_allowed=order_allowed,
        limits=ContractLimits(
            max_rows=50,  # Analysis results can be large
            max_predicates=8,
            max_update_fields=6
        )
    )