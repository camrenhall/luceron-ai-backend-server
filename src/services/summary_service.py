"""
Summary generation service using OpenAI API
"""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

import openai
from openai import AsyncOpenAI

from database.connection import get_db_pool

logger = logging.getLogger(__name__)

class SummaryService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.model = "gpt-5-mini"
        
        # Load system prompt - fail hard if not found
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / "conversation_summary.md"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract just the prompt content, skip the markdown headers
            lines = content.split('\n')
            # Find the first paragraph after the title
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('#'):
                    start_idx = i
                    break
            self.system_prompt = '\n'.join(lines[start_idx:])

    async def generate_summary(self, conversation_id: str) -> Optional[str]:
        """
        Generate a summary for a conversation using OpenAI API
        """
        try:
            db_pool = get_db_pool()
            
            async with db_pool.acquire() as conn:
                # Get all messages for the conversation
                messages = await conn.fetch("""
                    SELECT message_id, role, content, function_name, function_arguments, 
                           function_response, sequence_number, created_at
                    FROM agent_messages 
                    WHERE conversation_id = $1
                    ORDER BY sequence_number ASC
                """, conversation_id)
                
                if not messages:
                    logger.warning(f"No messages found for conversation {conversation_id}")
                    return None
                
                # Format messages for OpenAI
                formatted_messages = self._format_messages_for_prompt(messages)
                
                # Call OpenAI API
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Please summarize the following conversation:\n\n{formatted_messages}"}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                
                summary_content = response.choices[0].message.content.strip()
                logger.info(f"Generated summary for conversation {conversation_id}")
                
                return summary_content
                
        except Exception as e:
            logger.error(f"Failed to generate summary for conversation {conversation_id}: {e}")
            return None

    def _format_messages_for_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format database messages into a readable format for the AI prompt
        """
        formatted = []
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            seq_num = msg['sequence_number']
            
            # Handle JSON content
            if isinstance(content, (dict, list)):
                content_str = json.dumps(content, indent=2)
            else:
                content_str = str(content)
            
            message_parts = [f"Message #{seq_num} ({role}):"]
            message_parts.append(f"Content: {content_str}")
            
            # Add function call details if present
            if msg['function_name']:
                message_parts.append(f"Function: {msg['function_name']}")
                if msg['function_arguments']:
                    args_str = json.dumps(msg['function_arguments'], indent=2) if isinstance(msg['function_arguments'], (dict, list)) else str(msg['function_arguments'])
                    message_parts.append(f"Arguments: {args_str}")
                if msg['function_response']:
                    resp_str = json.dumps(msg['function_response'], indent=2) if isinstance(msg['function_response'], (dict, list)) else str(msg['function_response'])
                    message_parts.append(f"Response: {resp_str}")
            
            formatted.append("\n".join(message_parts))
        
        return "\n\n" + "\n\n---\n\n".join(formatted)

    async def create_or_update_summary(self, conversation_id: str) -> bool:
        """
        Create or update a summary for a conversation
        """
        try:
            # Generate summary content
            summary_content = await self.generate_summary(conversation_id)
            if not summary_content:
                return False
            
            db_pool = get_db_pool()
            
            async with db_pool.acquire() as conn:
                # Get message count and latest message
                message_info = await conn.fetchrow("""
                    SELECT COUNT(*) as total_messages, MAX(message_id) as last_message_id
                    FROM agent_messages 
                    WHERE conversation_id = $1
                """, conversation_id)
                
                if not message_info or message_info['total_messages'] == 0:
                    logger.warning(f"No messages found for conversation {conversation_id}")
                    return False
                
                # Check if summary already exists
                existing_summary = await conn.fetchrow("""
                    SELECT summary_id FROM agent_summaries 
                    WHERE conversation_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                """, conversation_id)
                
                if existing_summary:
                    # Update existing summary
                    await conn.execute("""
                        UPDATE agent_summaries 
                        SET summary_content = $1, 
                            messages_summarized = $2,
                            last_message_id = $3,
                            updated_at = NOW()
                        WHERE summary_id = $4
                    """, summary_content, message_info['total_messages'], 
                         message_info['last_message_id'], existing_summary['summary_id'])
                    
                    logger.info(f"Updated summary for conversation {conversation_id}")
                else:
                    # Create new summary
                    await conn.execute("""
                        INSERT INTO agent_summaries 
                        (conversation_id, last_message_id, summary_content, messages_summarized)
                        VALUES ($1, $2, $3, $4)
                    """, conversation_id, message_info['last_message_id'], 
                         summary_content, message_info['total_messages'])
                    
                    logger.info(f"Created new summary for conversation {conversation_id}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to create/update summary for conversation {conversation_id}: {e}")
            return False

# Global instance
summary_service = SummaryService()

async def trigger_summary_generation(conversation_id: str) -> None:
    """
    Async function to trigger summary generation in background
    This will be called from message create/update endpoints
    """
    try:
        await summary_service.create_or_update_summary(conversation_id)
    except Exception as e:
        logger.error(f"Background summary generation failed for conversation {conversation_id}: {e}")