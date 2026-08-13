from langchain_core.messages import SystemMessage, HumanMessage
from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractedMultipleChoiceGoal(BaseModel):
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
        constraints_block = "\n".join([f"  * {c}" for c in self.constraints])
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

class ExtractedSummarizationGoal(BaseModel):
    intent: str = Field(
        description="The high-level action required (e.g., 'Generate an executive summary of financial reports')."
    )
    target_subject: str = Field(
        description="The primary entity, document description, or topic that needs to be summarized."
    )
    summary_depth: str = Field(
        description="The expected length, style, or depth of the summary (e.g., 'bulleted list', 'one-page executive summary', 'detailed technical overview')."
    )
    required_focus_areas: List[str] = Field(
        default_factory=list,
        description="Key topics, metrics, or sections explicitly requested to be highlighted or included in the summary."
    )
    suggested_sources: Optional[List[str]] = Field(
        default=None,
        description="Explicit paths to files or folders mentioned in the prompt text containing the source material."
    )
    @property
    def text(self) -> str:
        focus_block = "\n".join([f"  * {focus}" for focus in self.goal.required_focus_areas]) if self.goal.required_focus_areas else "  * General comprehensive overview"
        sources_block = ", ".join(self.goal.suggested_sources) if self.goal.suggested_sources else "None Specified"
        
        return f"""
        =========================================
        CURRENT VERIFICATION HARNESS TARGETS (SUMMARIZATION):
        - INTENT: {self.goal.intent}
        - TARGET SUBJECT: {self.goal.target_subject}
        - REQUIRED FORMAT/DEPTH: {self.goal.summary_depth}

        CRITICAL AREAS OF FOCUS:
        {focus_block}

        TARGET REFERENCE SOURCES:
        * {sources_block}

        EXECUTION FRAMEWORK DIRECTIONS:
        Locate the source documents and extract a summary matching the requested DEPTH.
        Ensure every mandatory item under CRITICAL AREAS OF FOCUS is explicitly evaluated and present in your final summary submission.
        =========================================
        """

class ExtractedGenerationGoal(BaseModel):
    intent: str = Field(
        description="The high-level action required (e.g., 'Draft a cold sales outreach email sequence')."
    )
    target_format: str = Field(
        description="The exact asset type or container requested (e.g., 'Markdown blog post', 'JSON database mock', 'HTML Email')."
    )
    audience_tone: str = Field(
        description="The persona, target audience, or behavioral tone required (e.g., 'Persuasive and urgent', 'Technical but beginner-friendly')."
    )
    mandatory_sections: List[str] = Field(
        default_factory=list,
        description="Specific structural blocks, headers, or components that must exist in the final output."
    )
    required_keywords: List[str] = Field(
        default_factory=list,
        description="Specific terms, feature names, or phrases that must be explicitly included in the text."
    )

    @property
    def text(self) -> str:
        sections_block = "\n".join([f"  * {s}" for s in self.mandatory_sections]) if self.mandatory_sections else "  * Dynamic creative structure"
        keywords_block = ", ".join([f"'{k}'" for k in self.required_keywords]) if self.required_keywords else "None Specified"
        
        return f"""
        =========================================
        CURRENT VERIFICATION HARNESS TARGETS (GENERATION):
        - INTENT: {self.intent}
        - TARGET FORMAT: {self.target_format}
        - AUDIENCE & TONE: {self.audience_tone}

        MANDATORY STRUCTURAL SECTIONS:
        {sections_block}

        REQUIRED KEYWORDS / PHRASES:
        * {keywords_block}

        EXECUTION FRAMEWORK DIRECTIONS:
        Generate the requested asset from scratch adhering to the specified FORMAT and TONE.
        Your final output must contain all listed STRUCTURAL SECTIONS and explicitly use every item in the REQUIRED KEYWORDS array.
        =========================================
        """

class ExtractedCodeAnalysisGoal(BaseModel):
    intent: str = Field(
        description="The high-level action required (e.g., 'Optimize database indexing performance in a Python backend')."
    )
    language_framework: str = Field(
        description="The target programming language, database dialect, or framework (e.g., 'Python / FastAPI', 'PostgreSQL', 'TypeScript')."
    )
    analytical_focus: str = Field(
        description="The primary lens of evaluation (e.g., 'Security Audit', 'Bug Fixing', 'Performance Optimization', 'Refactoring')."
    )
    performance_or_quality_targets: List[str] = Field(
        default_factory=list,
        description="Explicit metrics or constraints required (e.g., 'O(log n) time complexity', 'No memory leaks', 'Avoid SQL injection hazards')."
    )
    suggested_sources: Optional[List[str]] = Field(
        default=None,
        description="Explicit code paths, repository folders, or file names mentioned in the prompt text."
    )

    @property
    def text(self) -> str:
        targets_block = "\n".join([f"  * {t}" for t in self.performance_or_quality_targets]) if self.performance_or_quality_targets else "  * Standard functional correctness"
        sources_block = ", ".join(self.suggested_sources) if self.suggested_sources else "None Specified"
        
        return f"""
        =========================================
        CURRENT VERIFICATION HARNESS TARGETS (CODE ANALYSIS):
        - INTENT: {self.intent}
        - LANGUAGES / FRAMEWORKS: {self.language_framework}
        - ANALYTICAL FOCUS: {self.analytical_focus}

        PERFORMANCE & QUALITY TARGETS:
        {targets_block}

        TARGET REFERENCE REPOSITORIES / FILES:
        * {sources_block}

        EXECUTION FRAMEWORK DIRECTIONS:
        Locate the codebase files. Audit or fix the target modules through the lens of the specified ANALYTICAL FOCUS.
        Your structural patches or analysis must strictly satisfy all listed PERFORMANCE & QUALITY TARGETS.
        =========================================
        """

class MultipleChoiceGoalExtractor:
    def __init__(self, llm):
        # Bind the Pydantic schema to your model
        self.structured_llm = llm.with_structured_output(ExtractedMultipleChoiceGoal)
        self.goal = None

    def extract_goal_data(self, user_input: str) -> ExtractedMultipleChoiceGoal:
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

class SummarizationGoalExtractor:
    def __init__(self, llm):
        # Bind the summarization schema to the LLM
        self.structured_llm = llm.with_structured_output(ExtractedSummarizationGoal)
        self.goal = None

    def extract_goal_data(self, user_input: str) -> ExtractedSummarizationGoal:
        system_prompt = (
            "You are a meta-analysis agent for an evaluation harness parsing text summarization requests.\n\n"
            "Your task is to break down the prompt into structural summary requirements.\n"
            "1. Abstract the high-level task into 'intent'.\n"
            "2. Identify what specific content or topic needs summarizing into 'target_subject'.\n"
            "3. Extract the requested length, format, or style into 'summary_depth'.\n"
            "4. Isolate any mandatory themes, metrics, or points to highlight into 'required_focus_areas'.\n"
            "5. Identify any specific reference documents mentioned by name into 'suggested_sources'."
        )

        messages = [
            SystemMessage(content=system_prompt),
            
            # Few-shot example for a structured summarization task
            HumanMessage(content=(
                "Please read through data/reports/q3_earnings.txt and provide a high-level executive summary. "
                "Make sure to explicitly highlight our net profit margins and the performance of the European sector."
            )),
            HumanMessage(content=str({
                "intent": "Generate a high-level executive summary of the Q3 earnings report.",
                "target_subject": "Q3 earnings report financials and sector performance.",
                "summary_depth": "High-level executive summary",
                "required_focus_areas": [
                    "Net profit margins",
                    "European sector performance"
                ],
                "suggested_sources": ["data/reports/q3_earnings.txt"]
            })),
            
            # Live harness prompt input
            HumanMessage(content=user_input)
        ]

        self.goal = self.structured_llm.invoke(messages)
        return self.goal

class GenerationGoalExtractor:
    def __init__(self, llm):
        self.structured_llm = llm.with_structured_output(ExtractedGenerationGoal)

    def extract_goal_data(self, user_input: str) -> ExtractedGenerationGoal:
        system_prompt = (
            "You are a meta-analysis agent for an evaluation harness parsing text generation requests.\n\n"
            "Your task is to break down the prompt into objective content generation boundaries.\n"
            "1. Abstract the high-level task into 'intent'.\n"
            "2. Identify the asset container or syntax into 'target_format'.\n"
            "3. Extract the target audience style, voice, or persona into 'audience_tone'.\n"
            "4. Isolate required layout sections, headers, or text blocks into 'mandatory_sections'.\n"
            "5. Pinpoint explicit terms, brands, or vocabulary words that must appear into 'required_keywords'."
        )

        messages = [
            SystemMessage(content=system_prompt),
            
            # Few-shot example for an asset generation request
            HumanMessage(content=(
                "Write a professional Markdown product announcement for our new software platform, 'ApexCloud'. "
                "The target audience is Enterprise CTOs. Make sure to include an 'Architecture Overview' section, "
                "a 'Pricing Tiers' section, and explicitly use the terms 'SOC2 Compliant' and 'Zero-Trust Infrastructure'."
            )),
            HumanMessage(content=str({
                "intent": "Draft a product announcement for ApexCloud targeting enterprise buyers.",
                "target_format": "Markdown document",
                "audience_tone": "Professional and enterprise-focused",
                "mandatory_sections": [
                    "Architecture Overview",
                    "Pricing Tiers"
                ],
                "required_keywords": [
                    "SOC2 Compliant",
                    "Zero-Trust Infrastructure",
                    "ApexCloud"
                ]
            })),
            
            # Live harness prompt input
            HumanMessage(content=user_input)
        ]

        # Returns the Pydantic instance containing its own .text property
        return self.structured_llm.invoke(messages)

class CodeAnalysisGoalExtractor:
    def __init__(self, llm):
        self.structured_llm = llm.with_structured_output(ExtractedCodeAnalysisGoal)

    def extract_goal_data(self, user_input: str) -> ExtractedCodeAnalysisGoal:
        system_prompt = (
            "You are a meta-analysis agent for an evaluation harness parsing code engineering requests.\n\n"
            "Your task is to break down the prompt into objective software engineering targets.\n"
            "1. Abstract the high-level task into 'intent'.\n"
            "2. Identify the language, runtime environment, or stack into 'language_framework'.\n"
            "3. Isolate the main action direction (security, performance, logic fixes) into 'analytical_focus'.\n"
            "4. Extract explicit metrics, asymptotic complexity, or error-handling rules into 'performance_or_quality_targets'.\n"
            "5. Pinpoint directories, paths, or code files mentioned into 'suggested_sources'."
        )

        messages = [
            SystemMessage(content=system_prompt),
            
            # Few-shot example for an engineering prompt
            HumanMessage(content=(
                "Review the authentication logic inside src/auth/jwt.py. Audit it for OWASP Top 10 security vulnerabilities, "
                "specifically checking for weak secret configurations, and ensure the execution maintains an O(1) runtime check."
            )),
            HumanMessage(content=str({
                "intent": "Audit JWT authentication logic for security vulnerabilities and performance bottlenecks.",
                "language_framework": "Python",
                "analytical_focus": "Security Audit and Performance Review",
                "performance_or_quality_targets": [
                    "OWASP Top 10 compliance",
                    "Fix weak secret configurations",
                    "O(1) lookup runtime complexity"
                ],
                "suggested_sources": ["src/auth/jwt.py"]
            })),
            
            # Live harness prompt input
            HumanMessage(content=user_input)
        ]

        return self.structured_llm.invoke(messages)
