"""
Example of Enterprise-Grade API Contract Testing
This eliminates ALL database synchronization issues
"""

async def test_cases_full_api_contract(api_client):
    """Test complete CRUD cycle via API contracts only"""
    
    # === CREATE ===
    case_data = {
        "client_name": "CRUD_TEST_Smith", 
        "client_email": "test@example.com",
        "status": "OPEN"
    }
    
    create_response = await api_client.post("/api/cases", json=case_data)
    assert create_response.status_code == 201
    case_id = create_response.json()["case_id"]
    
    # === READ (validates CREATE worked) ===
    read_response = await api_client.get(f"/api/cases/{case_id}")
    assert read_response.status_code == 200
    case = read_response.json()
    assert case["client_name"] == case_data["client_name"]
    assert case["status"] == "OPEN"
    
    # === UPDATE ===
    update_data = {"status": "IN_PROGRESS"}
    update_response = await api_client.put(f"/api/cases/{case_id}", json=update_data)
    assert update_response.status_code == 200
    
    # === READ (validates UPDATE worked) ===
    updated_case = await api_client.get(f"/api/cases/{case_id}")
    assert updated_case.json()["status"] == "IN_PROGRESS"
    
    # === DELETE ===
    delete_response = await api_client.delete(f"/api/cases/{case_id}")
    assert delete_response.status_code == 204
    
    # === READ (validates DELETE worked) ===
    deleted_response = await api_client.get(f"/api/cases/{case_id}")
    assert deleted_response.status_code == 404

async def test_documents_with_case_dependency(api_client):
    """Test foreign key relationships via API"""
    
    # Create parent case
    case_response = await api_client.post("/api/cases", json=case_data)
    case_id = case_response.json()["case_id"]
    
    # Create document with valid case_id
    doc_data = {
        "case_id": case_id,
        "original_file_name": "test.pdf",
        "status": "PENDING"
    }
    doc_response = await api_client.post("/api/documents", json=doc_data)
    assert doc_response.status_code == 201
    
    # Try to create document with invalid case_id
    invalid_doc_data = {**doc_data, "case_id": "non-existent-uuid"}
    invalid_response = await api_client.post("/api/documents", json=invalid_doc_data)
    assert invalid_response.status_code == 400  # API should reject this