# Document Management API

## Overview

This API provides endpoints for creating and updating document records as part of the AWS State Machine document processing pipeline. The system supports a two-phase workflow:

1. **Upload Time**: Create initial document record with original file metadata
2. **Processing Time**: Update document with processed file metadata and status changes

## Endpoints

### 1. Create Document Record

**Endpoint:** `POST /api/documents`

**Purpose:** Create a new document record when a file is first uploaded to the system.

**Authentication:** Required - `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "case_id": "123e4567-e89b-12d3-a456-426614174000",
  "original_file_name": "contract_2024.pdf",
  "original_file_size": 2048576,
  "original_file_type": "application/pdf",
  "original_s3_location": "us-east-1/documents-bucket",
  "original_s3_key": "uploads/2024/01/contract_2024.pdf",
  "batch_id": "batch-2024-001",
  "status": "uploaded"
}
```

**Required Fields:**
- `case_id` (UUID) - Must reference existing case
- `original_file_name` (string, max 500 chars)
- `original_file_size` (integer, > 0)
- `original_file_type` (string, max 100 chars)
- `original_s3_location` (string)
- `original_s3_key` (string, max 1000 chars)

**Optional Fields:**
- `batch_id` (string, max 255 chars)
- `status` (enum: uploaded|converted|analyzing|completed|failed, default: "uploaded")

**Success Response (201):**
```json
{
  "success": true,
  "document_id": "456e7890-e89b-12d3-a456-426614174001",
  "case_id": "123e4567-e89b-12d3-a456-426614174000",
  "original_file_name": "contract_2024.pdf",
  "status": "uploaded",
  "created_at": "2024-01-15T10:30:00.123456",
  "message": "Document record created successfully"
}
```

**Error Responses:**
- `400` - Invalid request data or missing case_id
- `404` - Case not found
- `409` - Document with same identifiers already exists
- `500` - Internal server error

### 2. Update Document Record

**Endpoint:** `PUT /api/documents/{document_id}`

**Purpose:** Update document record with processed file metadata and status changes.

**Authentication:** Required - `Authorization: Bearer <token>`

**Request Body (all fields optional for partial updates):**
```json
{
  "processed_file_name": "contract_2024.png",
  "processed_file_size": 1536000,
  "processed_s3_location": "us-east-1/processed-bucket",
  "processed_s3_key": "processed/2024/01/contract_2024.png",
  "status": "analyzed"
}
```

**Optional Fields:**
- `processed_file_name` (string, max 500 chars)
- `processed_file_size` (integer, > 0)
- `processed_s3_location` (string)
- `processed_s3_key` (string, max 1000 chars)
- `status` (enum: uploaded|converted|analyzing|completed|failed)

**Success Response (200):**
```json
{
  "success": true,
  "document_id": "456e7890-e89b-12d3-a456-426614174001",
  "updated_fields": ["processed_file_name", "processed_file_size", "status"],
  "status": "analyzed",
  "updated_at": "2024-01-15T10:35:00.123456",
  "message": "Document record updated successfully"
}
```

**Error Responses:**
- `400` - No fields provided for update or invalid data
- `404` - Document not found
- `500` - Internal server error

## AWS Pipeline Integration

### Phase 1: File Upload
```python
# AWS State Machine calls this when file is uploaded
response = requests.post(
    "https://api.example.com/api/documents",
    headers={"Authorization": "Bearer your-api-key"},
    json={
        "case_id": case_uuid,
        "original_file_name": uploaded_filename,
        "original_file_size": file_size_bytes,
        "original_file_type": mime_type,
        "original_s3_location": s3_bucket_region,
        "original_s3_key": s3_object_key,
        "batch_id": processing_batch_id,
        "status": "uploaded"
    }
)
document_id = response.json()["document_id"]
```

### Phase 2: Processing Complete
```python
# AWS State Machine calls this after PNG conversion
response = requests.put(
    f"https://api.example.com/api/documents/{document_id}",
    headers={"Authorization": "Bearer your-api-key"},
    json={
        "processed_file_name": "converted_file.png",
        "processed_file_size": converted_size,
        "processed_s3_location": processed_bucket,
        "processed_s3_key": processed_key,
        "status": "converted"
    }
)
```

### Phase 3: Analysis Complete
```python
# AWS State Machine calls bulk analysis endpoint
response = requests.post(
    "https://api.example.com/api/documents/analysis/bulk",
    headers={"Authorization": "Bearer your-api-key"},
    json={
        "analyses": [{
            "document_id": document_id,
            "case_id": case_id,
            "analysis_content": json.dumps(openai_analysis),
            "model_used": "o3",
            "analyzed_at": datetime.utcnow().isoformat(),
            "analysis_status": "completed"
        }]
    }
)

# Update document status to final state
requests.put(
    f"https://api.example.com/api/documents/{document_id}",
    headers={"Authorization": "Bearer your-api-key"},
    json={"status": "completed"}
)
```

## Status Workflow

Documents follow this status progression:

1. `uploaded` → Initial state when document record is created
2. `converted` → File has been converted to PNG format
3. `analyzing` → File is being analyzed by AI models
4. `completed` → Processing and analysis completed successfully
5. `failed` → Processing or analysis failed

## Database Schema Mapping

**Create Endpoint writes to:**
- `case_id`, `original_file_name`, `original_file_size`, `original_file_type`
- `original_s3_location`, `original_s3_key`, `batch_id`, `status`
- Auto-generated: `document_id`, `created_at`

**Update Endpoint modifies:**
- `processed_file_name`, `processed_file_size`
- `processed_s3_location`, `processed_s3_key`, `status`

## Validation Rules

### Create Document:
- `case_id` must reference existing case (foreign key constraint)
- All string fields are trimmed and validated for emptiness
- File size must be positive integer
- Status must be valid enum value

### Update Document:
- `document_id` must reference existing document
- At least one field must be provided for update
- Processed file size must be positive if provided
- String fields cannot be empty if provided

## Error Handling

- **Validation Errors**: Detailed field-level error messages
- **Foreign Key Violations**: Clear "Case not found" messages  
- **Not Found**: Specific resource identification
- **Database Errors**: Sanitized error messages for security
- **Performance Tracking**: All operations include processing time logging

## Security Features

- Mandatory Bearer token authentication on all endpoints
- SQL injection prevention via parameterized queries
- Input validation and sanitization
- Comprehensive error logging for monitoring

## Architecture Notes

- **Workflow Separation**: AWS State Machine workflows operate independently from internal agent workflows
- **Database Design**: `workflow_states` table reserved exclusively for internal agent workflows, not AWS pipeline executions
- **Clean API**: AWS document processing endpoints don't reference internal workflow tracking

This API provides a robust foundation for the AWS document processing pipeline with enterprise-grade error handling, validation, and performance monitoring.