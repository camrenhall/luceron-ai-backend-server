"""
Agent DB Testing Suite

Comprehensive testing for the /agent/db endpoint natural language database operations.

This package implements a two-phase testing strategy:
- Phase 1: REST API test data ecosystem creation
- Phase 2: Natural language operation validation

Test Categories:
- READ Operations: Simple queries, filtering, time-based, relationships, aggregation
- CREATE Operations: Case creation, documents, communications, agent state
- UPDATE Operations: Status changes, state transitions, context modifications
- Complex Workflows: Multi-step business scenarios
- Error Handling: Edge cases, security boundaries, malformed inputs
"""

__version__ = "1.0.0"
__author__ = "Claude Code Assistant"