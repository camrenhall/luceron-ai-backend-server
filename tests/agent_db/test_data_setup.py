"""
Phase 1: Test Data Ecosystem Creation via REST API
Creates comprehensive test data for agent/db endpoint validation
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from infrastructure import TestClient, UUIDTracker, extract_uuid_from_response, is_successful_response


class TestDataEcosystem:
    """Manages complete test data ecosystem creation and cleanup"""
    
    def __init__(self, client: TestClient, uuid_tracker: UUIDTracker):
        self.client = client
        self.uuid_tracker = uuid_tracker
        self.setup_data = {
            'cases': {},
            'documents': {},
            'communications': {},
            'conversations': {},
            'messages': {},
            'summaries': {},
            'context': {},
            'error_logs': {}
        }
    
    async def create_complete_ecosystem(self) -> Dict[str, Any]:
        """Create complete test data ecosystem"""
        print("  🏗️  Creating client portfolio...")
        await self._create_client_portfolio()
        
        print("  📄 Setting up document ecosystem...")
        await self._create_document_ecosystem()
        
        print("  📧 Generating communication history...")
        await self._create_communication_history()
        
        print("  🤖 Initializing agent states...")
        await self._create_agent_states()
        
        print("  📝 Seeding error logs...")
        await self._create_error_logs()
        
        return self.setup_data
    
    async def _create_client_portfolio(self):
        """Create 4 diverse test clients with cases"""
        clients = [
            {
                'name': 'Sarah Johnson',
                'email': 'sarah.johnson@email.com',
                'phone': '(555) 123-4567',
                'description': 'Active complex case'
            },
            {
                'name': 'Michael Chen', 
                'email': 'michael.chen@lawfirm.com',
                'phone': '(555) 234-5678',
                'description': 'Recently completed case'
            },
            {
                'name': 'Rebecca Martinez',
                'email': 'rebecca.martinez@company.com', 
                'phone': '(555) 345-6789',
                'description': 'Problematic case with issues'
            },
            {
                'name': 'David Thompson',
                'email': 'david.thompson@personal.com',
                'phone': '(555) 456-7890', 
                'description': 'Minimal activity case'
            }
        ]
        
        for client in clients:
            case_data = {
                'client_name': client['name'],
                'client_email': client['email'],
                'client_phone': client['phone']
            }
            
            response = await self.client.rest_request('POST', '/api/cases', case_data)
            
            if is_successful_response(response):
                case_id = extract_uuid_from_response(response, 'case_id')
                if case_id:
                    self.uuid_tracker.track('cases', case_id)
                    self.setup_data['cases'][client['name']] = {
                        'case_id': case_id,
                        'email': client['email'],
                        'phone': client['phone'],
                        'description': client['description']
                    }
                    print(f"    ✅ Created case for {client['name']}")
                else:
                    print(f"    ❌ Failed to extract case_id for {client['name']}")
            else:
                print(f"    ❌ Failed to create case for {client['name']}: {response}")
    
    async def _create_document_ecosystem(self):
        """Create documents with various processing states"""
        document_configs = [
            # Sarah Johnson's documents (complex states)
            {'client': 'Sarah Johnson', 'filename': 'Contract_Amendment.pdf', 'status': 'COMPLETED', 'size': 2457600},
            {'client': 'Sarah Johnson', 'filename': 'Financial_Records.xlsx', 'status': 'PROCESSING', 'size': 1024000},
            {'client': 'Sarah Johnson', 'filename': 'Legal_Brief.docx', 'status': 'COMPLETED', 'size': 512000},
            {'client': 'Sarah Johnson', 'filename': 'Evidence_Photos.zip', 'status': 'FAILED', 'size': 10485760},
            {'client': 'Sarah Johnson', 'filename': 'Correspondence.pdf', 'status': 'PENDING', 'size': 256000},
            
            # Michael Chen's documents (all completed)
            {'client': 'Michael Chen', 'filename': 'Settlement_Agreement.pdf', 'status': 'COMPLETED', 'size': 1536000},
            {'client': 'Michael Chen', 'filename': 'Case_Summary.docx', 'status': 'COMPLETED', 'size': 384000},
            
            # Rebecca Martinez's documents (mixed states)
            {'client': 'Rebecca Martinez', 'filename': 'Disputed_Invoice.pdf', 'status': 'FAILED', 'size': 768000},
            {'client': 'Rebecca Martinez', 'filename': 'Email_Thread.msg', 'status': 'COMPLETED', 'size': 204800},
            
            # David Thompson's document (minimal)
            {'client': 'David Thompson', 'filename': 'Initial_Complaint.pdf', 'status': 'PENDING', 'size': 1024000}
        ]
        
        for doc_config in document_configs:
            client_name = doc_config['client']
            if client_name in self.setup_data['cases']:
                case_id = self.setup_data['cases'][client_name]['case_id']
                
                document_data = {
                    'case_id': case_id,
                    'original_file_name': doc_config['filename'],
                    'original_file_size': doc_config['size'],
                    'original_file_type': 'application/pdf',  # Simplified
                    'original_s3_location': f's3://test-bucket/{doc_config["filename"]}',
                    'original_s3_key': f'documents/{case_id}/{doc_config["filename"]}',
                    'status': doc_config['status']
                }
                
                response = await self.client.rest_request('POST', '/api/documents', document_data)
                
                if is_successful_response(response):
                    document_id = extract_uuid_from_response(response, 'document_id')
                    if document_id:
                        self.uuid_tracker.track('documents', document_id)
                        
                        # Store document info for later reference
                        if client_name not in self.setup_data['documents']:
                            self.setup_data['documents'][client_name] = []
                        
                        self.setup_data['documents'][client_name].append({
                            'document_id': document_id,
                            'filename': doc_config['filename'],
                            'status': doc_config['status'],
                            'case_id': case_id
                        })
                        
                        print(f"    ✅ Created document {doc_config['filename']} for {client_name}")
                        
                        # Create analysis for completed documents
                        if doc_config['status'] == 'COMPLETED':
                            await self._create_document_analysis(document_id, case_id, doc_config['filename'])
                    else:
                        print(f"    ❌ Failed to extract document_id for {doc_config['filename']}")
                else:
                    print(f"    ❌ Failed to create document {doc_config['filename']}: {response}")
    
    async def _create_document_analysis(self, document_id: str, case_id: str, filename: str):
        """Create document analysis for completed documents"""
        analysis_data = {
            'document_id': document_id,
            'case_id': case_id,
            'analysis_content': json.dumps({
                'summary': f'Analysis of {filename} completed successfully',
                'key_points': ['Document processed', 'Content extracted', 'Metadata catalogued'],
                'confidence': 0.95,
                'processing_time': 45.2
            }),
            'analysis_status': 'COMPLETED',
            'model_used': 'gpt-4-vision-preview',
            'tokens_used': 1250
        }
        
        response = await self.client.rest_request('POST', f'/api/documents/{document_id}/analysis', analysis_data)
        
        if is_successful_response(response):
            analysis_id = extract_uuid_from_response(response, 'analysis_id')
            if analysis_id:
                self.uuid_tracker.track('document_analysis', analysis_id)
                print(f"      📊 Created analysis for {filename}")
    
    async def _create_communication_history(self):
        """Create communication history with various delivery states"""
        communication_configs = [
            # Sarah Johnson communications
            {'client': 'Sarah Johnson', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Document Upload Request', 'opened': True},
            {'client': 'Sarah Johnson', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Case Status Update', 'opened': False},
            {'client': 'Sarah Johnson', 'channel': 'email', 'direction': 'inbound', 'status': 'delivered', 'subject': 'Re: Document Upload Request', 'opened': None},
            {'client': 'Sarah Johnson', 'channel': 'sms', 'direction': 'outbound', 'status': 'delivered', 'subject': None, 'opened': None},
            {'client': 'Sarah Johnson', 'channel': 'email', 'direction': 'outbound', 'status': 'bounced', 'subject': 'Follow-up Required', 'opened': None},
            
            # Michael Chen communications  
            {'client': 'Michael Chen', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Case Initiation', 'opened': True},
            {'client': 'Michael Chen', 'channel': 'email', 'direction': 'inbound', 'status': 'delivered', 'subject': 'Re: Case Initiation', 'opened': None},
            {'client': 'Michael Chen', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Settlement Proposal', 'opened': True},
            {'client': 'Michael Chen', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Case Closure Confirmation', 'opened': True},
            
            # Rebecca Martinez communications
            {'client': 'Rebecca Martinez', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Document Processing Issues', 'opened': False},
            {'client': 'Rebecca Martinez', 'channel': 'email', 'direction': 'outbound', 'status': 'failed', 'subject': 'Urgent: Action Required', 'opened': None},
            {'client': 'Rebecca Martinez', 'channel': 'sms', 'direction': 'outbound', 'status': 'delivered', 'subject': None, 'opened': None},
            
            # David Thompson communications
            {'client': 'David Thompson', 'channel': 'email', 'direction': 'outbound', 'status': 'delivered', 'subject': 'Welcome to Our Legal Services', 'opened': False}
        ]
        
        for comm_config in communication_configs:
            client_name = comm_config['client']
            if client_name in self.setup_data['cases']:
                case_id = self.setup_data['cases'][client_name]['case_id']
                client_email = self.setup_data['cases'][client_name]['email']
                
                # Determine sender/recipient based on direction
                if comm_config['direction'] == 'outbound':
                    sender = 'legal@lawfirm.com'
                    recipient = client_email
                else:
                    sender = client_email
                    recipient = 'legal@lawfirm.com'
                
                # Create appropriate message content
                if comm_config['channel'] == 'sms':
                    message_content = "Important case update. Please check your email for details."
                else:
                    message_content = f"Legal communication regarding case {case_id[:8]}..."
                
                communication_data = {
                    'case_id': case_id,
                    'channel': comm_config['channel'],
                    'direction': comm_config['direction'],
                    'sender': sender,
                    'recipient': recipient,
                    'subject': comm_config['subject'],
                    'message_content': message_content,
                    'status': comm_config['status'],
                    'sent_at': datetime.utcnow().isoformat()
                }
                
                # Add opened_at if message was opened
                if comm_config.get('opened'):
                    communication_data['opened_at'] = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                
                response = await self.client.rest_request('POST', '/api/client-communications', communication_data)
                
                if is_successful_response(response):
                    comm_id = extract_uuid_from_response(response, 'communication_id')
                    if comm_id:
                        self.uuid_tracker.track('client_communications', comm_id)
                        
                        if client_name not in self.setup_data['communications']:
                            self.setup_data['communications'][client_name] = []
                        
                        self.setup_data['communications'][client_name].append({
                            'communication_id': comm_id,
                            'channel': comm_config['channel'],
                            'direction': comm_config['direction'],
                            'status': comm_config['status'],
                            'subject': comm_config['subject']
                        })
                        
                        print(f"    ✅ Created {comm_config['channel']} communication for {client_name}")
    
    async def _create_agent_states(self):
        """Create agent conversations, messages, and context"""
        conversation_configs = [
            {'client': 'Sarah Johnson', 'agent_type': 'CommunicationsAgent', 'status': 'ACTIVE', 'messages': 15, 'summaries': 2},
            {'client': 'Sarah Johnson', 'agent_type': 'AnalysisAgent', 'status': 'ACTIVE', 'messages': 25, 'summaries': 3},
            {'client': 'Michael Chen', 'agent_type': 'CommunicationsAgent', 'status': 'COMPLETED', 'messages': 8, 'summaries': 1},
            {'client': 'Michael Chen', 'agent_type': 'AnalysisAgent', 'status': 'COMPLETED', 'messages': 12, 'summaries': 2},
            {'client': 'Rebecca Martinez', 'agent_type': 'CommunicationsAgent', 'status': 'FAILED', 'messages': 3, 'summaries': 0}
        ]
        
        for conv_config in conversation_configs:
            client_name = conv_config['client']
            if client_name in self.setup_data['cases']:
                case_id = self.setup_data['cases'][client_name]['case_id']
                
                conversation_data = {
                    'case_id': case_id,
                    'agent_type': conv_config['agent_type'],
                    'status': conv_config['status']
                }
                
                response = await self.client.rest_request('POST', '/api/agent/conversations', conversation_data)
                
                if is_successful_response(response):
                    conv_id = extract_uuid_from_response(response, 'conversation_id')
                    if conv_id:
                        self.uuid_tracker.track('agent_conversations', conv_id)
                        
                        conv_key = f"{client_name}_{conv_config['agent_type']}"
                        self.setup_data['conversations'][conv_key] = {
                            'conversation_id': conv_id,
                            'client': client_name,
                            'agent_type': conv_config['agent_type'],
                            'status': conv_config['status']
                        }
                        
                        print(f"    ✅ Created {conv_config['agent_type']} conversation for {client_name}")
                        
                        # Create messages and summaries for this conversation
                        await self._create_agent_messages(conv_id, conv_config['messages'])
                        if conv_config['summaries'] > 0:
                            await self._create_agent_summaries(conv_id, conv_config['summaries'])
        
        # Create agent context entries
        await self._create_agent_context()
    
    async def _create_agent_messages(self, conversation_id: str, message_count: int):
        """Create messages for a conversation"""
        for i in range(message_count):
            role = 'user' if i % 3 == 0 else 'assistant' if i % 3 == 1 else 'system'
            
            message_data = {
                'conversation_id': conversation_id,
                'role': role,
                'content': {
                    'text': f'Sample {role} message {i+1} for conversation {conversation_id[:8]}',
                    'metadata': {'sequence': i+1}
                },
                'total_tokens': 45 + (i * 5),
                'model_used': 'gpt-4-turbo',
                'sequence_number': i + 1
            }
            
            response = await self.client.rest_request('POST', '/api/agent/messages', message_data)
            
            if is_successful_response(response):
                message_id = extract_uuid_from_response(response, 'message_id')
                if message_id:
                    self.uuid_tracker.track('agent_messages', message_id)
    
    async def _create_agent_summaries(self, conversation_id: str, summary_count: int):
        """Create summaries for a conversation"""
        for i in range(summary_count):
            summary_data = {
                'conversation_id': conversation_id,
                'summary_content': f'Summary {i+1} of conversation progress and key decisions made.',
                'messages_summarized': 5 + (i * 3)
            }
            
            response = await self.client.rest_request('POST', '/api/agent/summaries', summary_data)
            
            if is_successful_response(response):
                summary_id = extract_uuid_from_response(response, 'summary_id')
                if summary_id:
                    self.uuid_tracker.track('agent_summaries', summary_id)
    
    async def _create_agent_context(self):
        """Create agent context entries"""
        context_configs = [
            {'client': 'Sarah Johnson', 'agent_type': 'CommunicationsAgent', 'key': 'client_preferences', 'value': {'preferred_contact': 'email', 'timezone': 'EST'}},
            {'client': 'Michael Chen', 'agent_type': 'AnalysisAgent', 'key': 'case_insights', 'value': {'case_complexity': 'medium', 'completion_status': 'resolved'}},
            {'client': 'Rebecca Martinez', 'agent_type': 'CommunicationsAgent', 'key': 'escalation_flags', 'value': {'requires_attention': True, 'issues': ['failed_processing']}}
        ]
        
        for context_config in context_configs:
            client_name = context_config['client']
            if client_name in self.setup_data['cases']:
                case_id = self.setup_data['cases'][client_name]['case_id']
                
                context_data = {
                    'case_id': case_id,
                    'agent_type': context_config['agent_type'],
                    'context_key': context_config['key'],
                    'context_value': context_config['value']
                }
                
                response = await self.client.rest_request('POST', '/api/agent/context', context_data)
                
                if is_successful_response(response):
                    context_id = extract_uuid_from_response(response, 'context_id')
                    if context_id:
                        self.uuid_tracker.track('agent_context', context_id)
                        print(f"    ✅ Created agent context for {client_name}")
    
    async def _create_error_logs(self):
        """Create error log entries for testing"""
        error_configs = [
            {'component': 'email_service', 'severity': 'MEDIUM', 'message': 'Email delivery temporarily failed for recipient'},
            {'component': 'document_processor', 'severity': 'HIGH', 'message': 'Document processing failed due to unsupported format'},
            {'component': 'communication_handler', 'severity': 'MEDIUM', 'message': 'SMS delivery failed - invalid phone number'},
            {'component': 'analysis_engine', 'severity': 'HIGH', 'message': 'Analysis timeout exceeded for large document'},
            {'component': 'database_connection', 'severity': 'CRITICAL', 'message': 'Database connection pool exhausted - resolved'}
        ]
        
        for error_config in error_configs:
            error_data = {
                'component': error_config['component'],
                'error_message': error_config['message'],
                'severity': error_config['severity'],
                'context': {'test_generated': True, 'timestamp': datetime.utcnow().isoformat()}
            }
            
            response = await self.client.rest_request('POST', '/api/alert', error_data)
            
            if is_successful_response(response):
                # Error logs might not return IDs directly, so we'll track them differently
                print(f"    ✅ Created {error_config['severity']} error log")
    
    async def cleanup_all_data(self) -> bool:
        """Execute complete cleanup of all test data"""
        cleanup_success = True
        entity_types = self.uuid_tracker.get_cleanup_order()
        
        for entity_type in entity_types:
            uuids = self.uuid_tracker.get_tracked(entity_type)
            if uuids:
                print(f"  🗑️ Cleaning up {len(uuids)} {entity_type}...")
                
                for uuid_value in uuids:
                    try:
                        success = await self._cleanup_entity(entity_type, uuid_value)
                        if not success:
                            cleanup_success = False
                            print(f"    ❌ Failed to cleanup {entity_type}: {uuid_value}")
                    except Exception as e:
                        cleanup_success = False
                        print(f"    ❌ Error cleaning {entity_type} {uuid_value}: {e}")
        
        return cleanup_success
    
    async def _cleanup_entity(self, entity_type: str, uuid_value: str) -> bool:
        """Cleanup individual entity"""
        endpoint_map = {
            'agent_messages': f'/api/agent/messages/{uuid_value}',
            'agent_summaries': f'/api/agent/summaries/{uuid_value}',
            'agent_context': f'/api/agent/context/{uuid_value}',
            'document_analysis': f'/api/documents/analysis/{uuid_value}',
            'client_communications': f'/api/client-communications/{uuid_value}',
            'documents': f'/api/documents/{uuid_value}',
            'agent_conversations': f'/api/agent/conversations/{uuid_value}',
            'cases': f'/api/cases/{uuid_value}',
            'error_logs': f'/api/logs/{uuid_value}'  # May not exist
        }
        
        if entity_type in endpoint_map:
            try:
                response = await self.client.rest_request('DELETE', endpoint_map[entity_type])
                return is_successful_response(response) or response.get('_status_code') == 404  # 404 is OK for cleanup
            except Exception:
                return False
        
        return True  # Skip unknown entity types