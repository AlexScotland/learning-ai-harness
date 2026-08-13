from pydantic import BaseModel, Field
from enum import Enum

from goals.extractor_factory import GoalType

class ClassificationSchema(BaseModel):
    task_type: GoalType = Field(description="The primary classification of the user's prompt.")

class GoalRoutingManager:
    def __init__(self, llm, factory):
        self.llm = llm
        self.factory = factory
        # Bind the classification schema for a fast routing choice
        self.classifier = llm.with_structured_output(ClassificationSchema)

    def route_and_extract(self, prompt: str):
        # Step 1: The Manager uses the LLM to make the decision
        system_prompt = "Analyze the input prompt and determine its primary objective category."
        classification = self.classifier.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        # Step 2: The Manager uses the Factory to get the correct extractor instance
        extractor = self.factory.get_extractor(classification.task_type, self.llm)
        
        # Step 3: Run the specialized extractor and return the final payload
        return extractor.extract_goal_data(prompt)
