"""
Router component - maps natural language to resources and determines intent
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from agent_gateway.utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

@dataclass
class RouterResult:
    """Result from router operation"""
    resources: List[str]
    intent: str  # "READ" or "WRITE" 
    confidence: float
    reason: str

class Router:
    """Routes natural language requests to appropriate resources"""
    
    def __init__(self):
        self.available_resources = [
            "cases",
            "client_communications", 
            "documents",
            "document_analysis"
        ]
        # Confidence threshold for write operations
        self.write_confidence_threshold = 0.80
    
    async def route(
        self,
        natural_language: str,
        hints: Optional[Dict[str, Any]] = None
    ) -> RouterResult:
        """
        Route natural language request to resources and determine intent
        
        Args:
            natural_language: The natural language request
            hints: Optional hints about expected resources
            
        Returns:
            RouterResult with resources, intent, confidence, and reasoning
            
        Raises:
            ValueError: If write operation has insufficient confidence
            RuntimeError: If routing fails
        """
        try:
            # Use LLM to perform routing
            llm_client = get_llm_client()
            result = await llm_client.route_request(
                natural_language=natural_language,
                hints=hints,
                available_resources=self.available_resources
            )
            
            router_result = RouterResult(
                resources=result["resources"],
                intent=result["intent"],
                confidence=result["confidence"],
                reason=result["reason"]
            )
            
            # Apply confidence gating for write operations
            if router_result.intent == "WRITE" and router_result.confidence < self.write_confidence_threshold:
                # Phase 1: Reject low-confidence writes with clarification
                clarification = self._generate_clarification(natural_language, router_result)
                raise ValueError(
                    f"AMBIGUOUS_INTENT: {clarification}"
                )
            
            # Validate resources exist
            invalid_resources = [r for r in router_result.resources if r not in self.available_resources]
            if invalid_resources:
                raise ValueError(f"Invalid resources: {invalid_resources}")
            
            # Limit to K=2 default, K=3 only if clear join implied
            if len(router_result.resources) > 3:
                logger.warning(f"Too many resources ({len(router_result.resources)}), limiting to 3")
                router_result.resources = router_result.resources[:3]
            elif len(router_result.resources) > 2:
                logger.info(f"Using 3 resources due to implied join: {router_result.resources}")
            
            logger.info(
                f"Routing successful - Resources: {router_result.resources}, "
                f"Intent: {router_result.intent}, Confidence: {router_result.confidence:.2f}"
            )
            
            return router_result
            
        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(f"Router failed: {e}")
            raise RuntimeError(f"Routing failed: {str(e)}")
    
    def _generate_clarification(self, natural_language: str, result: RouterResult) -> str:
        """Generate a clarification question for ambiguous intent"""
        
        # Simple heuristics for common ambiguity patterns
        if "update" in natural_language.lower() or "change" in natural_language.lower():
            return "Which specific record do you want to update? Please provide a unique identifier."
        elif "create" in natural_language.lower() or "add" in natural_language.lower():
            return "What specific information should be included in the new record?"
        elif "status" in natural_language.lower():
            return "Do you want to view the current status or change it to a specific value?"
        else:
            return f"Are you looking to read information or make changes to {', '.join(result.resources)}?"
    
    def get_available_resources(self) -> List[str]:
        """Get list of available resources"""
        return self.available_resources.copy()

# Global router instance
_router: Optional[Router] = None

def get_router() -> Router:
    """Get the global router instance"""
    global _router
    if _router is None:
        _router = Router()
    return _router