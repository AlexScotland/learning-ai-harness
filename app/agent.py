import logging

from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage

from state import AgentStatus
from evaluator import EvaluationAction

logger = logging.getLogger(__name__)

class AgentRuntime:
    def __init__(
        self,
        planner,
        evaluator,
        task_executor,
        state,
        config
    ):
        self.planner = planner
        self.evaluator = evaluator
        self.task_executor = task_executor
        self.state = state
        self.state.initialize(system_prompt=self.load_agent_instructions(config.agent_path))
        self.max_iterations = config.max_iterations

    def load_agent_instructions(self, path):
        with open(path) as f:
            return f.read()

    def run(self, goal: str):
        self.state.goal = goal
        self.state.transition_to(AgentStatus.PLANNING)
        tasks = self.planner.create_plan(self.state)
        self.state.set_plan(tasks)
        self.state.transition_to(AgentStatus.EXECUTING)
        while task := self.state.get_current_task():
            last_result = self.task_executor.execute(
                task,
                self.state
            )

            evaluation = self.evaluator.evaluate(
                self.state,
                task
            )

            if evaluation.action == EvaluationAction.COMPLETE:
                return last_result


            if evaluation.action == EvaluationAction.REPLAN:
                tasks = self.planner.create_plan(
                    self.state
                )

                self.state.set_plan(tasks)
                continue

            self.state.complete_current_task()

        self.state.transition_to(
            AgentStatus.COMPLETED
        )
        return last_result

