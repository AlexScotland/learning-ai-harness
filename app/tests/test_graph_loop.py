"""Tests for the graph loop (v0, docs/graph-loop-designer.md).

Pinned behaviors:
  * schemas/graph.py — the frozen v0 validator: closed vocabulary, typed
    edges, exactly one entry, data-edge acyclicity, control edges only from
    verdict nodes with max_passes, side-effect nodes rejected inside
    parallel branches, on_failure/budget parsing.
  * components/graph_loop.py — execution semantics with FAKE components only
    (frozen v0 test rule: fakes assert; real LLM runs are smoke tests):
    serial walk, control-edge retries, node-level retry/skip/abort,
    budget ceilings, parallel determinism (same graph ⇒ identical
    conversation ORDER across 5 runs), branch isolation, event stream.
  * registry — the primitives namespace (one door) + describe() blocks.

Run from the ``app/`` directory:
    .venv-test/bin/pytest tests/ -v
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from langchain_core.messages import AIMessage

from components import (
    ComponentContext,
    ComponentRegistry,
    ComponentSlot,
    GraphLoop,
    register_builtin_components,
    register_graph_components,
)
from components.graph_loop import GraphBudgetError, GraphLoopError
from components.graph_store import GraphStore
from components.loops import LoopComponents
from goals.goal import Goal
from memory import ConversationMemory
from schemas.graph import GraphError, validate_graph
from state import AgentState
from tools.tool_registry import ToolRegistry

KILLER_GRAPH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "graphs", "killer-research.json"
)


# ── fakes (the frozen v0 test oracle: LLM + executor, never the harness) ────


class FakeStructured:
    def invoke(self, messages):
        return Goal(intent="fake intent")


class FakeLLM:
    """Just enough of the LLMProvider surface for construction."""

    def with_structured_output(self, schema):
        return FakeStructured()

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return AIMessage(content="fake-llm-answer")


class ScriptedCriticLLM:
    """The critic's LLM seam: a scripted pass/fail sequence (never the harness)."""

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls: list[str] = []
        self._n = 0

    def with_structured_output(self, schema):
        outer = self

        class _S:
            def invoke(self, messages):
                i = min(outer._n, len(outer.decisions) - 1)
                outer._n += 1
                d = outer.decisions[i]
                outer.calls.append(d)
                return types.SimpleNamespace(decision=d, feedback="scripted")

        return _S()


class FakeExecutor:
    """Records the tasks it ran; answers with the last word of the task text."""

    def __init__(self, answer="FROZEN-ANSWER", fail_times=0):
        self.answer = answer
        self.fail_times = fail_times
        self.tasks = []
        self.calls = 0

    def execute(self, task, state):
        self.calls += 1
        self.tasks.append(task)
        if self.calls <= self.fail_times:
            raise RuntimeError("fake executor exploded")
        return self.answer


class FlakyExecutor(FakeExecutor):
    """Fails while ``fail_times`` is true, then recovers — for node retries."""


def make_env(tmp_path, llm=None, executor=None):
    """A wired registry + store + activated graph loop (no network, no real LLM)."""
    llm = llm or FakeLLM()
    executor = executor or FakeExecutor()
    store = GraphStore(os.path.join(str(tmp_path), "graphs"))
    context = ComponentContext(llm=llm, tools=ToolRegistry(), config=None)
    registry = ComponentRegistry(context)
    register_builtin_components(registry, context)
    register_graph_components(registry, context, graph_store=store)
    registry.activate(ComponentSlot.LOOP, "graph")
    return {
        "registry": registry,
        "store": store,
        "loop": registry.active(ComponentSlot.LOOP),
        "executor": executor,
        "llm": llm,
    }


def run_turn(env, doc, agent_id="agent_under_test"):
    """Save+activate ``doc``, run ONE turn on a fresh AgentState."""
    env["store"].save("turn-graph", doc, name="test graph")
    env["store"].set_active("turn-graph")
    state = AgentState(
        agent_id=agent_id,
        conversation=ConversationMemory(),
        goal=Goal(intent="test goal"),
    )
    components = LoopComponents(executor=env["executor"])
    answer = env["loop"].run(components, state)
    return answer, state


def conversation_signature(state):
    """(type, content) pairs — what the determinism rule pins down."""
    return [(m.type, m.content) for m in state.conversation.messages]


# ── serial workflow graphs ───────────────────────────────────────────────────

SERIAL_GRAPH = {
    "nodes": {
        "prep": {"primitive": "prompt", "config": {"text": "Focus on concrete steps"}},
        "do": {"primitive": "act"},
        "judge": {"primitive": "critic"},
    },
    "edges": [
        {"from": "prep", "to": "do", "type": "data"},
        {"from": "do", "to": "judge", "type": "data"},
    ],
}

RETRY_GRAPH = {
    "nodes": {
        "prep": {"primitive": "prompt", "config": {"text": "Context for the work"}},
        "do": {"primitive": "act"},
        "judge": {"primitive": "critic"},
    },
    "edges": [
        {"from": "prep", "to": "do", "type": "data"},
        {"from": "do", "to": "judge", "type": "data"},
        {"from": "judge", "to": "do", "type": "control", "max_passes": 2},
    ],
}

PARALLEL_GRAPH = {
    "max_parallel": 2,
    "nodes": {
        "fanout": {
            "primitive": "parallel",
            "branches": [
                {
                    "name": "b1",
                    "graph": {
                        "nodes": {"gather1": {"primitive": "research", "config": {"task": "TASK-ONE"}}},
                        "edges": [],
                    },
                },
                {
                    "name": "b2",
                    "graph": {
                        "nodes": {"gather2": {"primitive": "research", "config": {"task": "TASK-TWO"}}},
                        "edges": [],
                    },
                },
            ],
        },
        "join": {"primitive": "merge"},
    },
    "edges": [{"from": "fanout", "to": "join", "type": "data"}],
}


# ── validator: the frozen v0 contract ────────────────────────────────────────


def test_serial_graph_validates():
    doc = validate_graph(SERIAL_GRAPH)
    assert doc.entry == "prep"
    assert doc.topo == ("prep", "do", "judge")


def test_shipped_killer_workflow_validates():
    with open(KILLER_GRAPH_PATH) as fh:
        doc = validate_graph(json.load(fh))
    assert doc.entry == "fanout"
    assert len(doc.control_out["judge"]) == 1
    assert doc.node("judge").id == "judge"


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (
            lambda g: g["nodes"]["prep"].update(primitive="vibecoding"),
            "unknown primitive",
        ),
        (
            lambda g: g["edges"].__setitem__(
                1, {"from": "judge", "to": "do", "type": "control"}
            ),
            "integer >= 1",  # control edge from a verdict node, but max_passes missing
        ),
        (
            lambda g: g["edges"].__setitem__(
                1, {"from": "prep", "to": "do", "type": "control", "max_passes": 2}
            ),
            "control edges must leave a verdict node",
        ),
        (
            lambda g: g["edges"].append({"from": "judge", "to": "prep", "type": "control", "max_passes": 0}),
            "integer >= 1",
        ),
        (
            lambda g: g["nodes"].update({"loner": {"primitive": "prompt", "config": {"text": "x"}}}),
            "expected exactly one entry node",
        ),
    ],
)
def test_contract_violations_are_rejected(tmp_path, mutate, expected):
    doc = json.loads(json.dumps(SERIAL_GRAPH))
    mutate(doc)
    with pytest.raises(GraphError, match=expected):
        validate_graph(doc)


def test_data_cycle_rejected_even_with_single_entry():
    doc = {
        "nodes": {
            "seed": {"primitive": "research"},  # entry: goal-only requires; provides 'result'
            "m": {"primitive": "merge"},
            "p": {"primitive": "parallel", "branches": [{"name": "b", "graph": {"nodes": {"r": {"primitive": "research"}}, "edges": []}}]},
        },
        "edges": [
            {"from": "seed", "to": "m", "type": "data"},  # result -> merge
            {"from": "m", "to": "p", "type": "data"},      # context -> parallel
            {"from": "p", "to": "m", "type": "data"},      # merged -> merge (the cycle)
        ],
    }
    with pytest.raises(GraphError, match="cycle"):
        validate_graph(doc)


def test_zero_entry_graphs_rejected():
    doc = {
        "nodes": {
            "m": {"primitive": "merge"},
            "p": {"primitive": "parallel", "branches": [{"name": "b", "graph": {"nodes": {"r": {"primitive": "research"}}, "edges": []}}]},
        },
        "edges": [
            {"from": "m", "to": "p", "type": "data"},
            {"from": "p", "to": "m", "type": "data"},
        ],
    }
    with pytest.raises(GraphError, match="entry"):
        validate_graph(doc)


def test_incompatible_data_edge_rejected():
    doc = {
        "nodes": {
            "r": {"primitive": "research"},
            "g": {"primitive": "gate"},
        },
        "edges": [{"from": "r", "to": "g", "type": "data"}],
    }
    with pytest.raises(GraphError, match="no compatible ports"):
        validate_graph(doc)


def test_entry_requiring_non_goal_input_rejected():
    with pytest.raises(GraphError, match="graph input 'goal'"):
        validate_graph({"nodes": {"do": {"primitive": "act"}}, "edges": []})


def test_self_edge_rejected():
    with pytest.raises(GraphError, match="itself"):
        validate_graph({"nodes": {"a": {"primitive": "prompt", "config": {"text": "x"}}}, "edges": [{"from": "a", "to": "a"}]})


def test_unknown_edge_target_rejected():
    with pytest.raises(GraphError, match="unknown node"):
        validate_graph(
            {
                "nodes": {
                    "a": {"primitive": "prompt", "config": {"text": "x"}},
                    "do": {"primitive": "act"},
                },
                "edges": [{"from": "a", "to": "ghost", "type": "data"}],
            }
        )


def test_side_effect_node_rejected_inside_parallel_branch():
    doc = json.loads(json.dumps(PARALLEL_GRAPH))  # deep copy: never mutate the shared constant
    doc["nodes"]["fanout"]["branches"][0]["graph"]["nodes"]["actor"] = {"primitive": "act"}
    with pytest.raises(GraphError, match="side-effect"):
        validate_graph(doc)


def test_branches_only_allowed_on_parallel():
    doc = {
        "nodes": {
            "do": {
                "primitive": "act",
                "branches": [{"name": "b", "graph": {"nodes": {"r": {"primitive": "research"}}, "edges": []}}],
            }
        },
        "edges": [],
    }
    with pytest.raises(GraphError, match="only valid on 'parallel'"):
        validate_graph(doc)


def test_branch_must_carry_inline_graph():
    doc = {
        "nodes": {
            "p": {"primitive": "parallel", "branches": [{"name": "b", "graph": "not-a-graph"}]}
        },
        "edges": [],
    }
    with pytest.raises(GraphError, match="inline 'graph'"):
        validate_graph(doc)


def test_on_failure_parsing():
    good = {"nodes": {"research": {"primitive": "research", "on_failure": "retry(2)"}}, "edges": []}
    assert validate_graph(good).node("research").on_failure == "retry"
    assert validate_graph(good).node("research").retries == 2
    with pytest.raises(GraphError, match="on_failure"):
        validate_graph(
            {"nodes": {"research": {"primitive": "research", "on_failure": "hope"}}, "edges": []}
        )


# ── engine: execution semantics (fakes only) ────────────────────────────────


def test_serial_turn_end_to_end(tmp_path):
    env = make_env(tmp_path, llm=ScriptedCriticLLM(["pass"]))
    answer, state = run_turn(env, SERIAL_GRAPH)
    assert answer == "FROZEN-ANSWER"
    assert state.status.value == "completed"
    events = state.metadata["graph_events"]
    assert [e["event"] for e in events].count("done") == 3
    # prompt committed its text; act/committing is merge's job only
    contents = [m.content for m in state.conversation.messages]
    assert any("concrete steps" in c for c in contents)
    assert env["store"].last_run("turn-graph")["status"] == "ok"


def test_retry_control_edge_rejects_then_recovers(tmp_path):
    env = make_env(tmp_path, llm=ScriptedCriticLLM(["fail", "pass"]))
    answer, state = run_turn(env, RETRY_GRAPH)
    assert env["executor"].calls == 2  # initial pass + one control re-run
    events = state.metadata["graph_events"]
    assert sum(e["event"] == "control" for e in events) == 1
    assert any("re-run from 'do'" in e.get("detail", "") for e in events if e["event"] == "control")
    assert state.status.value == "completed"


def test_retry_exhaustion_ends_the_turn(tmp_path):
    env = make_env(tmp_path, llm=ScriptedCriticLLM(["fail"]))
    answer, state = run_turn(env, RETRY_GRAPH)
    # initial + max_passes(2) re-runs, then the walk finishes (no infinite loop)
    assert env["executor"].calls == 3
    assert len(env["llm"].calls) == 3
    assert state.status.value == "completed"


def test_node_level_retry_policy(tmp_path):
    env = make_env(tmp_path, executor=FlakyExecutor(fail_times=1))
    doc = {
        "nodes": {"research": {"primitive": "research", "on_failure": "retry(1)"}},
        "edges": [],
    }
    answer, state = run_turn(env, doc)
    assert answer == "FROZEN-ANSWER"
    assert env["executor"].calls == 2
    events = [e["event"] for e in state.metadata["graph_events"]]
    assert events.count("failure") == 1
    assert "retry" in events


def test_node_level_skip_policy(tmp_path):
    env = make_env(tmp_path, executor=FlakyExecutor(fail_times=99))
    doc = {
        "nodes": {"research": {"primitive": "research", "on_failure": "skip"}},
        "edges": [],
    }
    answer, state = run_turn(env, doc)
    assert answer == ""  # nothing provided a result — the turn still ends
    assert env["executor"].calls == 1
    events = [e["event"] for e in state.metadata["graph_events"]]
    assert "skipped" in events
    assert state.status.value == "completed"


def test_fail_fast_is_the_default(tmp_path):
    env = make_env(tmp_path, executor=FlakyExecutor(fail_times=99))
    doc = {"nodes": {"research": {"primitive": "research"}}, "edges": []}
    env["store"].save("failing", doc)
    env["store"].set_active("failing")
    state = AgentState(agent_id="t", conversation=ConversationMemory(), goal=Goal(intent="g"))
    with pytest.raises(RuntimeError, match="fake executor exploded"):
        env["loop"].run(LoopComponents(executor=env["executor"]), state)
    assert state.status.value == "failed"
    assert env["store"].last_run("failing")["status"] == "failed"


def test_graph_budget_ceiling_is_binding(tmp_path):
    env = make_env(tmp_path)
    doc = {"budget": 1, "nodes": {"research": {"primitive": "research"}}, "edges": []}
    env["store"].save("tight", doc)
    env["store"].set_active("tight")
    state = AgentState(agent_id="t", conversation=ConversationMemory(), goal=Goal(intent="g"))
    with pytest.raises(GraphBudgetError):
        env["loop"].run(LoopComponents(executor=env["executor"]), state)
    assert state.status.value == "failed"
    assert env["store"].last_run("tight")["status"] == "failed"


def test_branch_budget_ceiling_is_binding(tmp_path):
    env = make_env(tmp_path)
    doc = {
        "nodes": {
            "fanout": {
                "primitive": "parallel",
                "branches": [
                    {
                        "name": "b1",
                        "budget": 1,  # below the research node's default allocation
                        "graph": {"nodes": {"gather": {"primitive": "research"}}, "edges": []},
                    }
                ],
            }
        },
        "edges": [],
    }
    validate_graph(doc)  # the ceiling is legal; it just cannot be served
    env["store"].save("tight-branch", doc)
    env["store"].set_active("tight-branch")
    state = AgentState(agent_id="t", conversation=ConversationMemory(), goal=Goal(intent="g"))
    with pytest.raises(GraphBudgetError):
        env["loop"].run(LoopComponents(executor=env["executor"]), state)


class TaskTextExecutor(FakeExecutor):
    """Answers with the task text itself — distinct per branch, so the
    determinism assertion pins a real ORDER, not a constant."""

    def execute(self, task, state):
        self.calls += 1
        self.tasks.append(task)
        return task.description


def test_parallel_determinism_across_five_runs(tmp_path):
    """FROZEN: same graph ⇒ identical conversation order across runs."""
    env = make_env(tmp_path, executor=TaskTextExecutor())
    signatures = []
    for i in range(5):
        _, state = run_turn(env, PARALLEL_GRAPH, agent_id=f"det-{i}")
        signatures.append(conversation_signature(state))
    assert all(s == signatures[0] for s in signatures)
    # goal first, then the TWO branch answers in DECLARED branch order (b1, b2)
    contents = [c for _, c in signatures[0]]
    joined = "\n".join(contents)
    assert joined.index("TASK-ONE") < joined.index("TASK-TWO")
    assert signatures[0][0][0] == "human"  # the goal banner


def test_parallel_branches_get_fresh_blackboards(tmp_path):
    """Branch commits never interleave into the shared conversation —
    only the declared merge node commits, serially, in declared order."""
    env = make_env(tmp_path, executor=FakeExecutor(answer=""))

    class CountingExecutor(FakeExecutor):
        def __init__(self):
            super().__init__(answer="")
            self.states = []

        def execute(self, task, state):
            self.states.append(state)
            self.calls += 1
            self.tasks.append(task)
            return f"ANS-{task.id}"

    counting = CountingExecutor()
    env["store"].save("iso", PARALLEL_GRAPH)
    env["store"].set_active("iso")
    state = AgentState(agent_id="t", conversation=ConversationMemory(), goal=Goal(intent="g"))
    env["loop"].run(LoopComponents(executor=counting), state)

    stores = {id(s) for s in counting.states}
    assert len(stores) == 2  # each branch ran on its OWN conversation store
    shared_store = id(state.conversation)
    assert shared_store not in stores
    contents = [m.content for m in state.conversation.messages]
    assert "ANS-gather1" in contents and "ANS-gather2" in contents
    assert contents.index("ANS-gather1") < contents.index("ANS-gather2")  # declared order


def test_no_registry_is_loud(tmp_path):
    loop = GraphLoop()
    state = AgentState(agent_id="t", conversation=ConversationMemory(), goal=Goal(intent="g"))
    with pytest.raises(GraphLoopError, match="ComponentRegistry"):
        loop.run(LoopComponents(executor=FakeExecutor()), state)


def test_no_active_graph_is_loud(tmp_path):
    env = make_env(tmp_path)  # store exists, but nothing saved/active
    state = AgentState(agent_id="t", conversation=ConversationMemory(), goal=Goal(intent="g"))
    with pytest.raises(GraphLoopError, match="no active graph"):
        env["loop"].run(LoopComponents(executor=env["executor"]), state)


# ── the registry door: primitives + graphs in describe() ────────────────────


def test_describe_exposes_primitive_vocabulary_and_graphs(tmp_path):
    env = make_env(tmp_path)
    env["store"].save("g1", SERIAL_GRAPH, name="serial")
    env["store"].set_active("g1")
    describe = env["registry"].describe()
    names = {p["name"] for p in describe["primitives"]}
    assert names == {"prompt", "research", "plan", "act", "critic", "gate", "merge", "parallel"}
    act = next(p for p in describe["primitives"] if p["name"] == "act")
    assert act["side_effects"] is True
    assert act["provides"] == ["result"]
    assert describe["graphs"]["active"] == "g1"
    assert describe["graphs"]["graphs"][0]["name"] == "serial"


def test_primitive_instance_is_cached_and_swappable(tmp_path):
    env = make_env(tmp_path)
    first = env["registry"].primitive("prompt")
    assert first is env["registry"].primitive("prompt")

    class MyPromptNode(type(first)):
        pass

    env["registry"].register_primitive("prompt", MyPromptNode)
    assert type(env["registry"].primitive("prompt")) is MyPromptNode  # re-registration swaps
