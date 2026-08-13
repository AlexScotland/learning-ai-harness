from enum import Enum
from typing import Type

# Standardize the supported types inside an analytical tracking Enum
class GoalType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    OPEN_QUESTION = "open_question"
    SUMMARIZATION = "summarization"
    GENERATION = "generation"
    CODE_ANALYSIS = "code_analysis"

# A scalable Factory to handle class mapping resolutions 
class GoalExtractorFactory:
    # 1. Store a clean lookup table matching types to their specialized engine classes
    _registry = {}

    @classmethod
    def register(cls, goal_type: GoalType, extractor_cls: Type):
        """Allows dynamically registering new engines without changing core code."""
        cls._registry[goal_type] = extractor_cls

    @classmethod
    def get_extractor(cls, goal_type: GoalType, llm):
        """Instantiates and returns the exact extractor class needed."""
        extractor_cls = cls._registry.get(goal_type)
        if not extractor_cls:
            raise ValueError(f"No extractor class has been registered for type: {goal_type}")
        return extractor_cls(llm)