from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from memory import ConversationMemory



class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"

@dataclass
class AgentState:
    agent_id: str
    conversation: ConversationMemory
    goal: str | None = None
    plan: list = field(default_factory=list)
    current_task: int = 0
    observations: list = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: AgentStatus = AgentStatus.INITIALIZING


    def add_message(self, message):
        self.conversation.add(message)

    def add_observation(self, observation):
        self.observations.append(observation)

    def set_plan(self, plan: list):
        self.plan = plan

    def get_current_task(self):
        if self.current_task >= len(self.plan):
            return None
    return self.plan[self.current_task]

    def complete_current_task(self):
        self.current_task += 1

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "goal": self.goal,
            "plan": self.plan,
            "current_task": self.current_task,
            "observations": self.observations,
            "metadata": self.metadata,
            "conversation": self.conversation.to_dict()
        }