"""FastAPI server wrapping the AI agent for HTTP access.

Stateless-by-design: the frontend owns the conversation thread. Every
``POST /api/chat`` carries the full prior conversation alongside the new
message, and the agent is built fresh per request — nothing of the thread
lives in this process, so a restart loses no conversation state.

Exposes:
  POST /api/chat   — send a message + prior conversation, get the answer
  GET  /health     — liveness probe
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Literal

from main import build_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-backend")

app = FastAPI(
    title="learning-ai-harness API",
    description="Stateless HTTP interface for the AI assistant agent",
    version="1.1.0",
)

# CORS — allow the chat-ui origin (and local dev) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ──────────────────────────────────


class ConversationTurn(BaseModel):
    role: Literal["user", "agent"]
    content: str = Field(..., min_length=1, max_length=50_000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000, description="The new user message")
    # Prior turns of the frontend thread, oldest first. Optional: an empty
    # list is a fresh conversation.
    conversation: list[ConversationTurn] = Field(
        default_factory=list,
        description="Prior conversation turns (oldest first), owned by the frontend.",
    )


class ChatResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str = "ok"


# ── Routes ───────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message (plus the frontend's prior conversation) to the AI
    agent and return its answer.

    The agent is stateless across requests: ``req.conversation`` is loaded
    fresh for this turn, and any new context the agent creates (goal, plan,
    tool results) is scoped to this call only.
    """
    try:
        history = [
            HumanMessage(content=turn.content) if turn.role == "user"
            else AIMessage(content=turn.content)
            for turn in req.conversation
        ]
        agent = build_agent()
        answer = agent.chat(req.message, history=history)
        return ChatResponse(answer=answer)
    except Exception as exc:
        logger.exception("Agent turn failed")
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
