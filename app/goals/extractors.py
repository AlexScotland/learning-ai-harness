from langchain_core.messages import SystemMessage, HumanMessage
from typing import List, Optional
from pydantic import BaseModel, Field

class ExtractedHarnessGoal(BaseModel):
    intent: str = Field(
        description="The high-level action/goal of the prompt (e.g., 'Answer a multiple-choice question')."
    )
    target_question: str = Field(
        description="The core question being asked in the prompt."
    )
    answer_options: List[str] = Field(
        description="A clean list of the multiple-choice options provided in the prompt, stripped of bullet points."
    )
    @property
    def text(self):
        return f"""
                =========================================
                CURRENT VERIFICATION HARNESS TARGETS:
                - INTENT: {self.intent}
                - TARGET QUESTION: {self.target_question}
                - MANDATORY CHANNELS / ANSWER OPTIONS:
                {chr(10).join([f"  * {opt}" for opt in self.answer_options])}

                EXECUTION FRAMEWORK DIRECTIONS:
                Use your file system tools to look up content validating the TARGET QUESTION.
                When finalizing your evaluation, you MUST select your answer strictly from one of the MANDATORY CHANNELS listed above. Do not ask for options; they are anchored here.
                =========================================
                """
    

class ExtractedOpenQuestionGoal(BaseModel):
    intent: str = Field(
        description="The high-level action required (e.g., 'Answer a long-form historical analysis question')."
    )
    target_question: str = Field(
        description="The core question or prompt instruction being asked."
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="A list of explicit rules, length limits, styling constraints, or structural criteria provided in the prompt."
    )
    suggested_sources: Optional[List[str]] = Field(
        default=None,
        description="Explicit paths to files or databases mentioned in the prompt text that the agent should look at."
    )
    
    @property
    def text(self):
        constraints_block = "\n".join([f"  * {c}" for c in self.constraints]) # 3. FIXED: Spelling typo 'contraints'
        sources_block = ", ".join(self.suggested_sources) if self.suggested_sources else "None Specified"
        return f"""
        =========================================
        CURRENT VERIFICATION HARNESS TARGETS (OPEN QUESTION):
        - INTENT: {self.intent}
        - TARGET INQUIRY: {self.target_question}

        CRITICAL FORMATTING CONSTRAINTS:
        {constraints_block}

        TARGET REFERENCE SOURCES:
        * {sources_block}

        EXECUTION FRAMEWORK DIRECTIONS:
        Utilize your tool inventory to scan target documentation. 
        Your final response must resolve the TARGET INQUIRY while strictly satisfying every constraint criteria item listed above.
        =========================================
        """


class MultipleChoiceGoalExtractor:
    def __init__(self, llm):
        # Bind the Pydantic schema to your model
        self.structured_llm = llm.with_structured_output(ExtractedHarnessGoal)
        self.goal = None

    def extract_goal_data(self, user_input: str) -> ExtractedHarnessGoal:
        system_prompt = (
            "You are a prompt analysis agent for an evaluation harness.\n\n"
            "Your task is to dissect the incoming prompt and map it to a structured goal.\n"
            "1. Extract the high-level intent into the 'intent' field.\n"
            "2. Isolate the core question being asked into 'target_question'.\n"
            "3. Clean and parse all available answer choices into the 'answer_options' list."
        )

        # Few-shot examples ensure the structural mapping is flawless
        messages = [
            SystemMessage(content=system_prompt),
            
            # Example 1
            HumanMessage(content=(
                "Please select one of the following answers.\n"
                "Question: What is 2+2?\n"
                "Answers: - 3\n- 4\n- 5"
            )),
            HumanMessage(content=str({
                "intent": "Answer a multiple-choice question about basic mathematics.",
                "target_question": "What is 2+2?",
                "answer_options": ["3", "4", "5"]
            })),
            
            # Your live harness prompt
            HumanMessage(content=user_input)
        ]

        # Returns a structured Pydantic object
        self.goal = self.structured_llm.invoke(messages)
        return self.goal

class OpenQuestionGoalExtractor:
    def __init__(self, llm):
        # Bind the open question schema to the LLM
        self.structured_llm = llm.with_structured_output(ExtractedOpenQuestionGoal)

    def extract_goal_data(self, user_input: str) -> ExtractedOpenQuestionGoal:
        system_prompt = (
            "You are a meta-analysis agent for an evaluation harness parsing open-ended questions.\n\n"
            "Your task is to break down the prompt into structural requirements.\n"
            "1. Abstract the high-level task into 'intent'.\n"
            "2. Isolate the exact core inquiry text into 'target_question'.\n"
            "3. Extract any specific formatting rules, source file restrictions, or tone constraints into 'constraints'.\n"
            "4. Identify any specific reference documents mentioned by name into 'suggested_sources'."
        )

        messages = [
            SystemMessage(content=system_prompt),
            
            # Few-shot example for a structured open question
            HumanMessage(content=(
                "Based on the files inside memory/pdfs/cmlto/, draft a professional summary explaining "
                "the circle of care. Keep your response under 3 paragraphs and write in a bulleted format."
            )),
            HumanMessage(content=str({
                "intent": "Draft an explanatory summary regarding the circle of care standard.",
                "target_question": "Explain what the circle of care is based on the documentation.",
                "constraints": [
                    "Keep response under 3 paragraphs.",
                    "Use a bulleted format.",
                    "Maintain a professional tone."
                ],
                "suggested_sources": ["memory/pdfs/cmlto/"]
            })),
            
            # Live harness prompt input
            HumanMessage(content=user_input)
        ]

        self.goal = self.structured_llm.invoke(messages)
        return self.goal