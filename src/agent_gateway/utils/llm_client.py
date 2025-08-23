"""
LLM client utilities for router and planner components
"""

import json
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class LLMClient:
    """Client for LLM operations (router and planner)"""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def route_request(
        self, 
        natural_language: str, 
        hints: Optional[Dict[str, Any]] = None,
        available_resources: list[str] = None
    ) -> Dict[str, Any]:
        """Route natural language to resources and determine intent"""
        
        available_resources = available_resources or [
            "cases", "client_communications", "documents", "document_analysis"
        ]
        
        system_prompt = f"""You are a router for a database query system. Your job is to:
1. Identify the most likely resources (tables) needed for the query
2. Determine if this is a READ or WRITE operation
3. Provide a confidence score (0.0-1.0)

Available resources: {', '.join(available_resources)}

Rules:
- Return exactly 2 resources by default, 3 only if a clear join is implied
- WRITE operations require high confidence (>0.8)
- READ operations can proceed with moderate confidence
- Focus on the most relevant resources

Respond with JSON in this exact format:
{{
    "resources": ["resource1", "resource2"],
    "intent": "READ" or "WRITE",
    "confidence": 0.85,
    "reason": "explanation of resource selection"
}}"""

        user_prompt = f"""Natural language query: "{natural_language}"
Hints: {json.dumps(hints) if hints else "none"}

Analyze this query and return the routing decision."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Fast, cheap model for routing
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent routing
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            
            # Validate required fields
            required_fields = ["resources", "intent", "confidence", "reason"]
            if not all(field in result for field in required_fields):
                raise ValueError("Missing required fields in router response")
            
            # Validate confidence range
            if not 0.0 <= result["confidence"] <= 1.0:
                raise ValueError("Confidence must be between 0.0 and 1.0")
            
            # Validate intent
            if result["intent"] not in ["READ", "WRITE"]:
                raise ValueError("Intent must be READ or WRITE")
            
            logger.info(f"Router result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse router JSON response: {e}")
            raise ValueError("Invalid JSON response from router")
        except Exception as e:
            logger.error(f"Router failed: {e}")
            raise RuntimeError(f"Router error: {str(e)}")
    
    async def plan_operation(
        self,
        natural_language: str,
        contracts: Dict[str, Any],
        intent: str,
        resources: list[str]
    ) -> Dict[str, Any]:
        """Convert natural language + contracts to internal DSL"""
        
        operation_type = "READ" if intent == "READ" else "WRITE"
        
        # Get current date for date-aware planning
        from datetime import datetime, timezone
        current_date = datetime.now(timezone.utc)
        current_date_str = current_date.strftime("%Y-%m-%d")
        current_datetime_str = current_date.isoformat()
        
        system_prompt = f"""You are a query planner that converts natural language to a strict internal DSL.

🚨 CRITICAL DATE AWARENESS 🚨
TODAY'S DATE IS: {current_date_str}
CURRENT YEAR IS: {current_date.year}

MANDATORY DATE CALCULATION RULES:
- "last 7 days" = created_at >= "{(current_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')}"
- "recent" = created_at >= "{(current_date - datetime.timedelta(days=3)).strftime('%Y-%m-%d')}"
- "today" = created_at >= "{current_date_str}"
- "this week" = created_at >= "{(current_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')}"

NEVER use dates from 2023 or 2024. The current year is {current_date.year}.
FOR "last 7 days", use: created_at >= "{(current_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')}"

IMPORTANT: Generate {operation_type} operations based on the natural language intent. 
For WRITE operations, choose between INSERT or UPDATE based on the request context.

Available resources and their contracts:
{json.dumps(contracts, indent=2)}

DSL Format Rules:

READ operations:
{{
    "steps": [{{
        "op": "READ",
        "resource": "table_name",
        "select": ["field1", "field2"],
        "where": [
            {{"field": "field_name", "op": "=", "value": "value"}},
            {{"field": "date_field", "op": ">=", "value": "2024-01-01"}}
        ],
        "order_by": [{{"field": "created_at", "dir": "desc"}}],
        "limit": 100
    }}]
}}

UPDATE operations (MUST include PK equality and limit 1):
{{
    "steps": [{{
        "op": "UPDATE",
        "resource": "table_name",
        "where": [
            {{"field": "id_field", "op": "=", "value": "specific_id"}}
        ],
        "update": {{
            "field1": "new_value",
            "field2": "another_value"
        }},
        "limit": 1
    }}]
}}

INSERT operations (DB generates IDs, no explicit IDs):
{{
    "steps": [{{
        "op": "INSERT", 
        "resource": "table_name",
        "values": {{
            "field1": "value1",
            "field2": "value2"
        }}
    }}]
}}

Critical Rules:
- UPDATE: MUST include primary key field in WHERE with equality (=) and limit: 1
- INSERT: NEVER include ID fields (they are auto-generated)
- Only use fields marked as readable (SELECT) or writable (INSERT/UPDATE)
- Only use operators allowed for each field per contracts
- Use proper data types for values
- Only reference resources from: {resources}
- For UPDATE, identify the primary key field (usually ends with _id)

Respond with valid JSON DSL only, no explanations."""

        user_prompt = f"""Convert this to DSL: "{natural_language}"
Expected operation type: {intent}
Target resources: {resources}

Generate the internal DSL:"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",  # Better model for precise planning
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,  # Zero temperature for deterministic planning
                max_tokens=800
            )
            
            dsl_content = response.choices[0].message.content.strip()
            
            # Remove any markdown code blocks
            if dsl_content.startswith("```"):
                lines = dsl_content.split('\n')
                dsl_content = '\n'.join(lines[1:-1])
            
            result = json.loads(dsl_content)
            
            # Basic validation
            if "steps" not in result or not isinstance(result["steps"], list):
                raise ValueError("DSL must have 'steps' array")
            
            if not result["steps"]:
                raise ValueError("DSL must have at least one step")
            
            logger.info(f"Planner result: {json.dumps(result, indent=2)}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse planner JSON response: {e}")
            raise ValueError("Invalid JSON response from planner")
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            raise RuntimeError(f"Planner error: {str(e)}")

# Singleton instance - will be initialized with config
llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Get the LLM client instance"""
    if llm_client is None:
        raise RuntimeError("LLM client not initialized")
    return llm_client

def init_llm_client(api_key: str) -> None:
    """Initialize the LLM client"""
    global llm_client
    llm_client = LLMClient(api_key)