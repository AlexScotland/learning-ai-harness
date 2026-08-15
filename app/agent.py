import logging

from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage

from state import AgentStatus
from evaluator import EvaluationAction

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Runs a goal through plan -> execute -> evaluate.

    Exposes two entry points:
      * ``run()``   - one-shot execution of the goal already set on ``state``.
      * ``chat()``  - one conversational turn: extract a Goal from the user's
                      message, execute it, and return the answer. The shared
                      ``ConversationMemory`` persists across turns, so the
                      agent keeps context for a full multi-turn conversation.
    """

    def __init__(
        self,
        planner,
        evaluator,
        task_executor,
        state,
        config,
        goal_extractor=None,
    ):
        self.planner = planner
        self.evaluator = evaluator
        self.task_executor = task_executor
        self.state = state
        self.goal_extractor = goal_extractor
        self.state.initialize(system_prompt=self.load_agent_instructions(config.agent_path))
        self.max_iterations = config.max_iterations

    def load_agent_instructions(self, path):
        with open(path) as f:
            return f.read()

    def _execute(self):
        """Run the plan for the goal currently set on ``state`` and return the
        final answer (the last task result)."""
        self.state.add_goal()
        self.state.transition_to(AgentStatus.PLANNING)
        tasks = self.planner.create_plan(self.state)
        self.state.set_plan(tasks)
        self.state.transition_to(AgentStatus.EXECUTING)

        last_result = None
        while task := self.state.get_current_task():
            last_result = self.task_executor.execute(task, self.state)

            evaluation = self.evaluator.evaluate(self.state, task)

            if evaluation.action == EvaluationAction.COMPLETE:
                return last_result

            if evaluation.action == EvaluationAction.REPLAN:
                tasks = self.planner.create_plan(self.state)
                self.state.set_plan(tasks)
                continue

            self.state.complete_current_task()

        self.state.transition_to(AgentStatus.COMPLETED)
        return last_result

    def run(self):
        """One-shot execution of the goal already set on ``state``."""
        return self._execute()

    def chat(self, user_input):
        """Handle one conversational turn.

        Extracts a Goal from ``user_input``, executes it, and returns the
        agent's answer. Conversation history is retained in ``state.conversation``
        so successive turns form a coherent multi-turn dialogue.
        """
        if self.goal_extractor is not None:
            self.state.goal = self.goal_extractor.extract(user_input)
        else:
            self.state.goal = user_input

        logger.info("Starting agent turn for input: %r", user_input)
        result = self._execute()
        logger.info("Agent turn completed. Result: %s", result)
        return result
