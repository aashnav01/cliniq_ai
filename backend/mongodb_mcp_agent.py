"""
mongodb_mcp_agent.py — ClinIQ MongoDB MCP Agent

Exposes a natural language interface over the clinical MongoDB Atlas database,
powered by Gemini 2.0 Flash as the reasoning engine.

Architecture:
  User Query (NL)
      ↓  Gemini 2.0 Flash
  MongoDB filter spec (JSON)
      ↓  motor (async pymongo)
  MongoDB Atlas  →  structured results
      ↓
  Gemini insight annotation
      ↓
  JSON response to frontend / hackathon judges

In production this agent would connect to the @mongodb-js/mongodb-mcp-server
via stdio MCP transport (managed by fastmcp). For the demo, the MCP query
translation and execution are handled inline for latency and reliability.

Endpoints:
  POST /api/agent/query              — Natural language → results
  GET  /api/agent/collections/stats  — Document counts per collection
  GET  /api/agent/collections/recent — Last N records across all types
  GET  /api/agent/examples           — Pre-built example queries for the UI
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

router = APIRouter(prefix="/api/agent", tags=["MCP Clinical Agent"])


# ── Request / Response models ─────────────────────────────────────────────────

class AgentQueryRequest(BaseModel):
    query: str = Field(
        ...,
        examples=[
            "Show all critical red flags from today",
            "How many patients had drug interactions this week?",
            "Find SOAP notes mentioning chest pain",
            "List patients with renal impairment",
            "What was the most common diagnosis today?",
        ]
    )
    limit: Optional[int] = Field(10, ge=1, le=50)


class ExampleQuery(BaseModel):
    label: str
    query: str
    collection: str
    icon: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/query")
async def natural_language_query(request: AgentQueryRequest):
    """
    **MongoDB MCP Agent** — ask any clinical question in plain English.

    Gemini 2.0 Flash interprets the query, generates a MongoDB filter,
    motor executes it against MongoDB Atlas, and results are returned
    with an AI-generated clinical insight.

    **Example queries:**
    - *"Show all critical red flags from today"*
    - *"How many patients had drug interactions this week?"*
    - *"Find SOAP notes mentioning chest pain"*
    - *"List all patients with renal impairment"*
    - *"What was the most common analysis type this shift?"*
    """
    from gemini_service import gemini_service
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")
    result = await gemini_service.agent_query(request.query, request.limit or 10)
    return result


@router.get("/collections/stats")
async def collection_stats():
    """
    Return document counts for all four clinical MongoDB collections.
    Useful for a dashboard overview of data volume.
    """
    from mongo_service import mongo_service
    db = mongo_service.db
    return {
        "database":      "cliniq",
        "powered_by":    "MongoDB Atlas",
        "collections": {
            "analyses":      await db["analyses"].count_documents({}),
            "patients":      await db["patients"].count_documents({}),
            "shifts":        await db["shifts"].count_documents({}),
            "prescriptions": await db["prescriptions"].count_documents({}),
        }
    }


@router.get("/collections/recent")
async def recent_activity(limit: int = 5):
    """
    Return the most recent clinical records across all types —
    useful for a live activity feed on the analytics dashboard.
    """
    from mongo_service import mongo_service
    recent = await mongo_service.get_analyses_any(limit)
    return {
        "recent": recent,
        "count":  len(recent),
    }


@router.get("/examples", response_model=List[ExampleQuery])
async def example_queries():
    """
    Return a curated list of example queries for the UI's query picker.
    These demonstrate the range of the MCP agent's capabilities.
    """
    return [
        ExampleQuery(
            label="Critical red flags today",
            query="Show all analyses with critical red flags from today",
            collection="analyses",
            icon="🚨"
        ),
        ExampleQuery(
            label="Drug interaction checks",
            query="List all prescription safety checks that had critical drug interactions",
            collection="prescriptions",
            icon="💊"
        ),
        ExampleQuery(
            label="Chest pain presentations",
            query="Find all SOAP notes mentioning chest pain",
            collection="analyses",
            icon="🫀"
        ),
        ExampleQuery(
            label="Renal impairment patients",
            query="List patients with renal impairment or on dialysis",
            collection="patients",
            icon="🩺"
        ),
        ExampleQuery(
            label="Recent handover briefings",
            query="Show the last 10 shift handover analyses",
            collection="analyses",
            icon="📋"
        ),
        ExampleQuery(
            label="High NEWS2 scores",
            query="Find SOAP notes where the NEWS2 score was high severity",
            collection="analyses",
            icon="📊"
        ),
        ExampleQuery(
            label="Active shifts today",
            query="Show all shifts that started today",
            collection="shifts",
            icon="🏥"
        ),
        ExampleQuery(
            label="Dengue / tropical presentations",
            query="Find clinical notes mentioning dengue or malaria",
            collection="analyses",
            icon="🌡️"
        ),
    ]
