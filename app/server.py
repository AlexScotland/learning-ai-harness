"""FastAPI server wrapping the AI agent for HTTP access.

Stateless-by-design: the frontend owns the conversation thread. Every
``POST /api/chat`` carries the full prior conversation alongside the new
message, and the agent is built fresh per request — nothing of the thread
lives in this process, so a restart loses no conversation state.

Component hot-swap lives on the process-shared registry (see main.py):
swapping a slot or activating a preset takes effect from the very next
request, with no restart and no per-request state needed.

Exposes:
  POST /api/chat               — send a message + prior conversation, get the answer
  GET  /api/components        — live slot/preset configuration (described)
  POST /api/components/activate — activate a preset, or one slot alias
  GET  /health                — liveness probe
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Literal

from components import ComponentSlot
from main import build_agent, get_registry

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


class ActivateRequest(BaseModel):
    preset: str | None = Field(default=None, description="Activate a whole preset, e.g. 'fast'.")
    slot: str | None = Field(default=None, description="Activate one slot, e.g. 'executor'.")
    alias: str | None = Field(default=None, description="The alias to activate for the slot.")


class HealthResponse(BaseModel):
    status: str = "ok"


# ── Routes ───────────────────────────────────


@app.get("/api/components")
def components_status():
    """Describe the live component configuration: for every slot the active
    alias and the available alternatives, plus all named presets."""
    return get_registry().describe()


@app.post("/api/components/activate")
def activate_components(req: ActivateRequest):
    """Swap components in at runtime.

    Exactly one of ``preset`` (a named slot set) or ``slot`` + ``alias``
    (a single slot) may be given. The swap affects the next /api/chat turn;
    an in-flight turn finishes on the component set it started with.
    """
    if bool(req.preset) == bool(req.slot):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of 'preset' or 'slot' (with 'alias' when slot is set).",
        )

    registry = get_registry()
    try:
        if req.preset:
            registry.activate_preset(req.preset)
        else:
            try:
                slot = ComponentSlot(req.slot)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown slot {req.slot!r} (expected one of: {', '.join(s.value for s in ComponentSlot)})",
                )
            if not req.alias:
                raise HTTPException(status_code=400, detail="'alias' is required with 'slot'.")
            registry.activate(slot, req.alias)
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"activation failed: {exc}")

    return registry.describe()


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
