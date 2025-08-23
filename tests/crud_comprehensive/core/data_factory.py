"""
Lightweight test data factory
Generates realistic but clearly-marked test data with constraint awareness
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from faker import Faker

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config


class DataFactory:
    """Lightweight test data generator"""
    
    def __init__(self):
        self.config = get_config()
        self.fake = Faker()
        self.created_uuids: Dict[str, List[str]] = {}
        
    def track_uuid(self, entity_type: str, uuid_value: str):
        """Track created UUID for cleanup"""
        if entity_type not in self.created_uuids:
            self.created_uuids[entity_type] = []
        self.created_uuids[entity_type].append(str(uuid_value))
    
    def generate_case(self, **overrides) -> Dict[str, Any]:
        """Generate test case data"""
        case_id = str(uuid.uuid4())
        self.track_uuid('cases', case_id)
        
        data = {
            "client_name": f"{self.config.test_data_prefix}_{self.fake.company()}",
            "client_email": f"test.{self.fake.user_name()}@crud-test.example.com",
            "client_phone": self.fake.phone_number()[:20],  # Respect DB constraint
            "status": "OPEN"
        }
        data.update(overrides)
        return data, case_id
    
    def generate_document(self, case_id: str, **overrides) -> Dict[str, Any]:
        """Generate test document data"""
        doc_id = str(uuid.uuid4())
        self.track_uuid('documents', doc_id)
        
        data = {
            "case_id": case_id,
            "original_file_name": f"test_doc_{self.fake.uuid4()}.pdf",
            "original_file_size": self.fake.random_int(min=1000, max=10000000),
            "original_file_type": "application/pdf",
            "original_s3_location": f"s3://test-bucket/{self.config.test_data_prefix.lower()}/",
            "original_s3_key": f"test-docs/{self.fake.uuid4()}.pdf",
            "status": "PENDING"
        }
        data.update(overrides)
        return data, doc_id
    
    def generate_communication(self, case_id: str, **overrides) -> Dict[str, Any]:
        """Generate test communication data"""
        comm_id = str(uuid.uuid4())
        self.track_uuid('client_communications', comm_id)
        
        data = {
            "case_id": case_id,
            "channel": "email",
            "direction": "outgoing",
            "status": "sent",
            "sender": f"test.sender@{self.config.test_data_prefix.lower().replace('_', '-')}.example.com",
            "recipient": f"test.recipient@{self.config.test_data_prefix.lower().replace('_', '-')}.example.com",
            "subject": f"Test Communication - {self.fake.sentence()}",
            "message_content": f"Test message content: {self.fake.paragraph()}"
        }
        data.update(overrides)
        return data, comm_id
    
    def generate_agent_conversation(self, **overrides) -> Dict[str, Any]:
        """Generate test agent conversation data"""
        conv_id = str(uuid.uuid4())
        self.track_uuid('agent_conversations', conv_id)
        
        data = {
            "agent_type": "CommunicationsAgent",
            "status": "ACTIVE",
            "total_tokens_used": 0
        }
        data.update(overrides)
        return data, conv_id
    
    def generate_agent_message(self, conversation_id: str, sequence_number: int = 1, **overrides) -> Dict[str, Any]:
        """Generate test agent message data"""
        msg_id = str(uuid.uuid4())
        self.track_uuid('agent_messages', msg_id)
        
        data = {
            "conversation_id": conversation_id,
            "role": "user",
            "content": {"text": f"Test message: {self.fake.sentence()}"},
            "total_tokens": self.fake.random_int(min=10, max=100),
            "model_used": "gpt-4-turbo",
            "sequence_number": sequence_number
        }
        data.update(overrides)
        return data, msg_id
    
    def generate_agent_context(self, case_id: str, **overrides) -> Dict[str, Any]:
        """Generate test agent context data"""
        context_id = str(uuid.uuid4())
        self.track_uuid('agent_context', context_id)
        
        data = {
            "case_id": case_id,
            "agent_type": "CommunicationsAgent",
            "context_key": f"test_key_{self.fake.uuid4()[:8]}",
            "context_value": {
                "test_data": True,
                "created_by": "crud_test_suite",
                "value": self.fake.sentence()
            }
        }
        data.update(overrides)
        return data, context_id
    
    def generate_error_log(self, **overrides) -> Dict[str, Any]:
        """Generate test error log data"""
        error_id = str(uuid.uuid4())
        self.track_uuid('error_logs', error_id)
        
        data = {
            "component": f"{self.config.test_data_prefix}_test_component",
            "error_message": f"Test error: {self.fake.sentence()}",
            "severity": "medium",
            "context": {
                "test_data": True,
                "created_by": "crud_test_suite"
            }
        }
        data.update(overrides)
        return data, error_id
    
    def get_cleanup_order(self) -> List[str]:
        """Get entity types in proper cleanup order (children first)"""
        return [
            'agent_messages',
            'agent_summaries', 
            'agent_context',
            'document_analysis',
            'client_communications',
            'documents',
            'agent_conversations',
            'error_logs',
            'cases'
        ]
    
    def get_tracked_uuids(self) -> Dict[str, List[str]]:
        """Get all tracked UUIDs for cleanup"""
        return self.created_uuids.copy()