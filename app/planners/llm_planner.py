import json

from langchain_core.messages import SystemMessage, HumanMessage
from planners.interface import Planner
from task import Task


class LLMPlanner(Planner):

    def __init__(self, llm):
        self.llm = llm

    def parse_tasks(self, content):
        raw_tasks = json.loads(content)
        return [
            Task(
                id=t["id"],
                description=t["description"]
            )
            for t in raw_tasks
        ]

    def create_plan(
        self,
        state
    ) -> list[Task]:

        prompt = f"""
            You are a planning agent.

            Your job is to break a user goal into executable tasks.

            Rules:
            - Create small, concrete tasks.
            - Do not execute tools.
            - Do not solve the problem.
            - Only describe the steps.

            Goal:
            {state.goal}

            {Task.llm_format()}
            """

        response = self.llm.invoke(
            [
                SystemMessage(content=prompt)
            ]
        )
        return self.parse_tasks(response.content)