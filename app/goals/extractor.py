"""The single goal extractor.

One class, one ``extract()``. There is no router and no factory: instead of
classifying the prompt into a category and then dispatching to a per-category
extractor (two LLM calls, N schemas, N registrations), this makes ONE
structured-output call against the single ``Goal`` schema and normalizes the
result. Everything a prompt asks for that has no dedicated field lands in the
open ``requirements`` list or the ``output_spec`` dict.
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage

from .goal import Goal
from .examples import EXAMPLES


class GoalExtractor:
    def __init__(self, llm):
        # Bind the single Goal schema for one-shot structured extraction.
        self.structured_llm = llm.with_structured_output(Goal)

    def _build_messages(self, user_input: str) -> list:
        system = (
            "You are a prompt-analysis agent for an evaluation harness.\n"
            "Extract a Goal from the incoming prompt.\n\n"
            "Rules:\n"
            "1. 'intent': the high-level action the prompt asks for (one sentence).\n"
            "2. 'requirements': EVERY concrete requirement or deliverable the prompt "
            "asks for, one item each, independently verifiable. Do NOT merge several "
            "requirements into one item. This is the primary field.\n"
            "3. 'constraints': any rules, length limits, tone, style, format, or "
            "structural criteria. Empty list if none.\n"
            "4. 'suggested_sources': file paths or documents the prompt explicitly "
            "names. null if none.\n"
            "5. 'output_spec': an optional structured tail holding prompt-specific "
            "structure verbatim - e.g. multiple-choice answer_options, "
            "required_keywords, mandatory_sections, target_format. Copy such items "
            "exactly as given. Omit it (null) when the prompt has no such structure.\n\n"
            "Return a valid Goal object. Do not invent requirements the prompt did "
            "not state."
        )
        messages: list = [SystemMessage(content=system)]
        for example in EXAMPLES:
            messages.append(HumanMessage(content=example["prompt"]))
            messages.append(HumanMessage(content=str(example["goal"])))
        messages.append(HumanMessage(content=user_input))
        return messages

    def extract(self, user_input: str) -> Goal:
        """One structured call -> a normalized Goal."""
        raw = self.structured_llm.invoke(self._build_messages(user_input))
        return Goal.from_raw(raw)