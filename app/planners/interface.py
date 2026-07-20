from abc import ABC, abstractmethod

from state import AgentState
from task import Task


class Planner(ABC):

    @abstractmethod
    def create_plan(
        self,
        state: AgentState
    ) -> list[Task]:
        pass