"""FastAPI server wrapping the AI agent for HTTP access.

Exposes:
  POST /api/chat   — send a message, get the agent's answer
  GET  /health     — liveness probe
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from main import build_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-backend")

app = FastAPI(
    title="learning-ai-harness API",
    description="HTTP interface for the AI assistant agent",
    version="1.0.0",
)

# CORS — allow the chat-ui container (and local dev) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build the agent once at startup (shared across all requests)
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        logger.info("Building agent (first request)…")
        _agent = build_agent()
        logger.info("Agent ready.")
    return _agent


# ── Schemas ──────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000, description="User message")


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str = "ok"
    agent_loaded: bool


# ── Routes ───────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", agent_loaded=_agent is not None)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to the AI agent and return its answer."""
    try:
        agent = get_agent()
        answer = agent.chat(req.message)
        return ChatResponse(answer=answer)
    except Exception as exc:
        logger.exception("Agent turn failed")
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
