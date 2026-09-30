"""Built-in component factories and the standard presets.

Every factory takes a ComponentContext and returns a fresh component, so the
same set of implementations can be registered anywhere (REPL, server, tests)
and swapped at runtime.

Presets
-------
default   - the classic LLM pipeline:
            goal extraction -> LLM planning -> LLM+tools execution ->
            criteria evaluation, plan-execute-evaluate loop.
fast      - fewer LLM calls: no planning round-trip (single-task plan),
            trimmed context memory. Still uses the LLM to think and act.
offline   - fully deterministic, zero LLM calls: passthrough goal, trivial
            plan, echo executor, unconditional evaluation, direct loop.
            Useful for tests and for exercising the harness with no model.
"""
from evaluator import AlwaysCompleteEvaluator, TaskEvaluator
from goals.extractor import GoalExtractor
from goals.passthrough import PassthroughGoalResolver
from memory import ConversationMemory, TrimmedMemory
from planners.llm_planner import LLMPlanner
from planners.trivial import TrivialPlanner
from tasks.echo_executor import EchoExecutor
from tasks.task_executor import LLMTaskExecutor

from .context import ComponentContext
from .loops import DirectLoop, PlanExecuteLoop
from .registry import ComponentRegistry
from .slots import ComponentSlot as Slot

# ── Factories (factory(ctx) -> component) ────────────────────────────


def _require_llm(ctx: ComponentContext):
    if ctx.llm is None:
        raise RuntimeError(
            "ComponentContext.llm is required for this component. Provide context.llm, "
            "or activate the 'offline' preset, which needs no model."
        )


def _require_tools(ctx: ComponentContext):
    if ctx.tools is None:
        raise RuntimeError(
            "ComponentContext.tools is required for the LLM executor. Provide context.tools."
        )


def make_goal_resolver(ctx: ComponentContext):
    _require_llm(ctx)
    return GoalExtractor(llm=ctx.llm)


def make_passthrough_goal(ctx: ComponentContext):
    return PassthroughGoalResolver()


def make_planner(ctx: ComponentContext):
    _require_llm(ctx)
    return LLMPlanner(llm=ctx.llm)


def make_trivial_planner(ctx: ComponentContext):
    return TrivialPlanner()


def make_executor(ctx: ComponentContext):
    _require_llm(ctx)
    _require_tools(ctx)
    max_iterations = getattr(ctx.config, "max_iterations", 30)
    return LLMTaskExecutor(llm=ctx.llm, tool_registry=ctx.tools, max_iterations=max_iterations)


def make_echo_executor(ctx: ComponentContext):
    return EchoExecutor()


def make_evaluator(ctx: ComponentContext):
    return TaskEvaluator()


def make_always_complete(ctx: ComponentContext):
    return AlwaysCompleteEvaluator()


def make_memory(ctx: ComponentContext):
    # Per-agent: each create() call builds a fresh store.
    return ConversationMemory()


def make_trimmed_memory(ctx: ComponentContext):
    limit = int(ctx.extras.get("memory_max_messages", 20))
    return TrimmedMemory(max_messages=limit)


def make_loop_plan_execute(ctx: ComponentContext):
    return PlanExecuteLoop()


def make_loop_direct(ctx: ComponentContext):
    return DirectLoop()


# ── Registration table ───────────────────────────────────────────────

COMPONENT_ALIASES = {
    Slot.GOAL_RESOLVER: {
        "default": (make_goal_resolver, "1.0.0", "LLM goal extraction (GoalExtractor)"),
        "passthrough": (make_passthrough_goal, "1.0.0", "LLM-free: raw input becomes the goal"),
    },
    Slot.PLANNER: {
        "default": (make_planner, "1.0.0", "LLM task planning (LLMPlanner)"),
        "trivial": (make_trivial_planner, "1.0.0", "LLM-free: single task for the whole goal"),
    },
    Slot.EXECUTOR: {
        "default": (make_executor, "1.0.0", "LLM + tools execution with budget (LLMTaskExecutor)"),
        "echo": (make_echo_executor, "1.0.0", "Deterministic echo; no LLM (tests / offline)"),
    },
    Slot.EVALUATOR: {
        "default": (make_evaluator, "1.0.0", "Success-criteria evaluation (TaskEvaluator)"),
        "always_complete": (make_always_complete, "1.0.0", "Unconditional COMPLETE (pins loop behavior)"),
    },
    Slot.MEMORY: {
        "default": (make_memory, "1.0.0", "Full conversation history (per-agent)"),
        "trimmed": (make_trimmed_memory, "1.0.0", "Bounded context: system message + last N messages"),
    },
    Slot.LOOP: {
        "plan_execute": (make_loop_plan_execute, "1.0.0", "Classic plan -> execute -> evaluate with replan"),
        "direct": (make_loop_direct, "1.0.0", "Single pass: goal straight through the executor"),
    },
}

PRESETS = {
    "default": {
        Slot.GOAL_RESOLVER: "default",
        Slot.PLANNER: "default",
        Slot.EXECUTOR: "default",
        Slot.EVALUATOR: "default",
        Slot.MEMORY: "default",
        Slot.LOOP: "plan_execute",
    },
    "fast": {
        Slot.GOAL_RESOLVER: "default",
        Slot.PLANNER: "trivial",
        Slot.EXECUTOR: "default",
        Slot.EVALUATOR: "default",
        Slot.MEMORY: "trimmed",
        Slot.LOOP: "plan_execute",
    },
    "offline": {
        Slot.GOAL_RESOLVER: "passthrough",
        Slot.PLANNER: "trivial",
        Slot.EXECUTOR: "echo",
        Slot.EVALUATOR: "always_complete",
        Slot.MEMORY: "default",
        Slot.LOOP: "direct",
    },
}


def register_builtin_components(
    registry: ComponentRegistry,
    context: ComponentContext | None = None,
    activate_preset: str = "default",
) -> None:
    """Register every built-in alias + preset; activate the default preset.

    The first alias registered in each slot becomes its initial active one
    (registry construction rule), so after this call the registry already
    runs the `default` pipeline; activate_preset() then pins the exact set.
    """
    if context is not None:
        registry.context = context
    for slot, aliases in COMPONENT_ALIASES.items():
        for alias, (factory, version, description) in aliases.items():
            registry.register(slot, alias, factory, version=version, description=description)
    for name, mapping in PRESETS.items():
        registry.register_preset(name, mapping)
    registry.activate_preset(activate_preset)
