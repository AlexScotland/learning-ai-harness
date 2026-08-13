from agent import AgentRuntime
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember
from tools.pdf import read_pdf_page, get_pdf_info
from tools.tool_registry import ToolRegistry
from state import AgentState
from planners.llm_planner import LLMPlanner
from tasks.task_executor import LLMTaskExecutor
from evaluator import TaskEvaluator
from agent_config import AgentConfig
from goals.extractor_factory import GoalType, GoalExtractorFactory
from goals.extractors import (
    MultipleChoiceGoalExtractor,
    OpenQuestionGoalExtractor,
    SummarizationGoalExtractor,
    GenerationGoalExtractor,
    CodeAnalysisGoalExtractor
)
from goals.manager import GoalRoutingManager

ALL_TOOLS = [get_pdf_info, read_pdf_page, list_files]


import logging
logging.basicConfig(level=logging.INFO)


def main(prompt):
    llm=OllamaProvider()
    # Setup the goal extractor factory and register the multiple-choice extractor
    goal_factory = GoalExtractorFactory()
    goal_factory.register(GoalType.MULTIPLE_CHOICE, MultipleChoiceGoalExtractor)
    goal_factory.register(GoalType.OPEN_QUESTION, OpenQuestionGoalExtractor)
    goal_factory.register(GoalType.SUMMARIZATION, SummarizationGoalExtractor)
    goal_factory.register(GoalType.GENERATION, GenerationGoalExtractor)
    goal_factory.register(GoalType.CODE_ANALYSIS, CodeAnalysisGoalExtractor)
    # Get the goal extractor instance for the multiple-choice type
    router = GoalRoutingManager(llm=llm, factory=goal_factory)

    planner = LLMPlanner(llm=llm)
    config = AgentConfig()
    tools_registry = ToolRegistry()
    tools_registry.register_many(ALL_TOOLS)
    conversation_memory = ConversationMemory()
    task_executor = LLMTaskExecutor(
        llm=llm,
        tool_registry=tools_registry,
        max_iterations=config.max_iterations
    )
    goal = router.route_and_extract(prompt)
    # goal = GoalExtractor(llm=llm).extract_goal_data(prompt)
    state = AgentState(agent_id="agent_1", goal=goal, conversation=conversation_memory)
    logging.info("Agent state initialized: %s", state.to_dict())    
    agent = AgentRuntime(
        planner=planner,
        task_executor=task_executor,
        evaluator=TaskEvaluator(),
        state=state,
        config=AgentConfig()
    )
    logging.info("Starting agent execution...")
    result = agent.run()
    logging.info("Agent execution completed. Result: %s", result)


if __name__ == "__main__":
    main("""
        Please select one of the following answers to the scenario below. Only respond with the answer text, do not include any other text or formatting.
        Question:  Mary is a specialized chemistry MLT in a laboratory that does significant volumes of hormone testing on various analyzers. A vendor representative approached her and asked if she would be interested in providing some raw data for a paper on estrogen levels in post-menopausal women. They assured her that patients’ names would not be published and they were strictly interested in the women’s ages and estrogen results. What should Mary do?

        Answers:
            - Mary should pursue the offer as it could be an excellent opportunity for her and the other staff to get involved in a study and provide them with additional knowledge that would benefit their patients.
            - Mary should not consider the offer as the collection of personal information, even age and sex, is limited and can never be shared.
            - Mary should take the matter to the Medical Director for their review and/or discuss with the hospital’s Ethics Committee.
            - Mary should anonymize the results and provide the information to the vendor.
         """)
