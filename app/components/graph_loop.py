"""GraphLoop (alias ``loop.graph``): run a validated graph as an AgentLoop.

Registry-client pattern (same as the other loops): the loop receives the
per-turn component snapshot (``LoopComponents``) and never touches the
registry itself, except for the ``primitives`` namespace — one door — and
the graph store that holds the active JSON document.

Execution semantics (frozen v0 contract):
  * fresh execution, serial top-level walk in deterministic data-edge
    topological order (the engine is the only thing that ever commits to
    the shared conversation, and it does so serially);
  * ``control`` edges (retries) only re-run the declared suffix, at most
    ``max_passes`` times, and only when the verdict did not pass;
  * ``parallel`` branches run concurrently with a fresh blackboard each;
    only a declared ``merge`` node commits branch output, in declared order;
  * budgets (executor-budget units): per-node, per-branch and graph
    ceilings; the graph ceiling is binding; exceed → fail-fast;
  * per-node ``on_failure``: abort (default) | skip | retry(n);
  * every node emits start/result/done (+ failure/skipped/retry) events,
    JSON-serializable, recorded on the state and the graph store — the
    API + future-canvas seam.
"""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from state import AgentState, AgentStatus
from memory import ConversationMemory
from schemas.graph import (
    DEFAULT_MAX_PARALLEL,
    DEFAULT_NODE_BUDGET,
    GraphDoc,
    NodeSpec,
    PRIMITIVES,
    validate_graph,
)

from .graph_store import get_graph_store
from .loops import AgentLoop, LoopComponents
from .primitives.base import NodeInputError

_MISSING = object()


class GraphLoopError(RuntimeError):
    """The graph loop is misconfigured (no registry / store / active graph)."""


class GraphBudgetError(RuntimeError):
    """A budget ceiling (node/branch/graph) would be exceeded."""


def _loop_running() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _verdict_failed(outputs: dict) -> bool:
    """A control edge is 'taken' when the source's verdict did not pass."""
    if not outputs:
        return False
    if "pass" in outputs:
        return outputs["pass"] is False
    verdict = outputs.get("verdict")
    if isinstance(verdict, dict):
        return verdict.get("pass") is False
    if verdict is not None and hasattr(verdict, "decision"):
        return str(verdict.decision).lower() == "fail"
    return False


class EventSink:
    """Thread-safe collector of JSON-serializable node events on the state."""

    def __init__(self, state):
        self.state = state
        self._lock = threading.Lock()
        state.metadata.setdefault("graph_events", [])

    def append(self, record: dict):
        with self._lock:
            self.state.metadata["graph_events"].append(record)

    def events(self) -> list[dict]:
        with self._lock:
            return list(self.state.metadata["graph_events"])


class OutputLog:
    """The per-run blackboard: (node_id, typed outputs) in execution order.

    Input resolution is 'most recently executed upstream provider' — which
    is exactly what makes re-run suffixes (retry loops) see the FRESH values.
    """

    def __init__(self, seed: dict | None = None):
        self.entries: list[tuple[str, dict]] = []
        if seed:
            self.entries.append(("__context__", dict(seed)))

    def record(self, node_id: str, outputs: dict):
        self.entries.append((node_id, dict(outputs)))

    def latest(self, node_id: str) -> dict | None:
        for nid, outputs in reversed(self.entries):
            if nid == node_id:
                return outputs
        return None

    def resolve(self, type_name: str):
        for _, outputs in reversed(self.entries):
            if type_name in outputs:
                return outputs[type_name]
        return _MISSING


class BudgetLedger:
    """One budget ceiling (executor-budget units), thread-safe."""

    def __init__(self, cap: int | None):
        self.cap = cap
        self.used = 0
        self._lock = threading.Lock()

    def allocate(self, amount: int, who: str = ""):
        if not amount or amount <= 0:
            return
        with self._lock:
            if self.cap is not None and self.used + amount > self.cap:
                raise GraphBudgetError(
                    f"node {who!r} needs {amount} executor-budget unit(s); ceiling "
                    f"{self.cap} would be exceeded ({self.used} already allocated)"
                )
            self.used += amount


class NodeState:
    """The ``state`` a node's ``run(state, config)`` receives (contract door).

    Read ``requires`` with ``get`` / ``get_optional``, record ``provides``
    with ``out``. ``goal`` is the graph input (resolved Goal of the turn).
    Branch nodes operate on their OWN fresh blackboard (fresh conversation
    store); only top-level commits and declared ``merge`` nodes touch the
    shared conversation.
    """

    def __init__(self, engine: "_GraphEngine", node: NodeSpec):
        self._engine = engine
        self._node = node
        self._outputs: dict = {}

    # ── surface (the 5-line contract) ───────────────────────────
    @property
    def node_id(self) -> str:
        return self._node.id

    @property
    def node_budget(self) -> int:
        return self._node.budget if self._node.budget is not None else DEFAULT_NODE_BUDGET

    @property
    def agent(self):
        return self._engine.state

    @property
    def goal(self):
        return self._engine.state.goal

    @property
    def conversation(self):
        return self._engine.state.conversation

    @property
    def ctx(self):
        return self._engine.loop.context

    @property
    def components(self):
        return self._engine.components

    @property
    def max_parallel(self) -> int:
        return self._engine.graph.max_parallel

    @property
    def branches(self):
        return tuple(self._node.branches)

    # ── blackboard ───────────────────────────────────────────────
    def get(self, type_name: str):
        if type_name == "goal":
            if self.goal is None:
                raise NodeInputError(
                    f"node {self.node_id!r} requires the graph input 'goal', but no goal is resolved"
                )
            return self.goal
        value = self._engine.log.resolve(type_name)
        if value is _MISSING:
            raise NodeInputError(
                f"node {self.node_id!r} requires input {type_name!r}, but no upstream node "
                f"provided it (missing edge, or upstream skipped)"
            )
        return value

    def get_optional(self, type_name: str):
        try:
            return self.get(type_name)
        except NodeInputError:
            return None

    def inputs(self):
        """Upstream (node_id, outputs) pairs in DECLARED edge order (merge)."""
        engine = self._engine
        out = []
        for src in engine.graph.incoming.get(self._node.id, ()):
            value = engine.log.latest(src)
            out.append((src, value if value is not None else {}))
        return out

    def out(self, type_name: str, value):
        self._outputs[type_name] = value

    def outputs(self) -> dict:
        return dict(self._outputs)

    def run_branches(self, branches, max_parallel: int, context):
        return self._engine.run_branches(branches, max_parallel, context)


class _GraphEngine:
    """One execution of one graph (the root graph, or one parallel branch)."""

    def __init__(
        self,
        loop: "GraphLoop",
        components: LoopComponents,
        state,
        graph: GraphDoc,
        sink: EventSink,
        ledgers: list[BudgetLedger],
        branch: str | None = None,
        seed: dict | None = None,
    ):
        self.loop = loop
        self.components = components
        self.state = state
        self.graph = graph
        self.sink = sink
        self.ledgers = ledgers
        self.branch = branch
        self.log = OutputLog(seed)
        self.taken: dict[int, int] = {}
        self._instances: dict[str, object] = {}

    # ── events ───────────────────────────────────────────────────
    def _emit(self, event: str, node: NodeSpec | None = None, detail: str | None = None):
        record = {"event": event, "at": round(time.time(), 3)}
        if node is not None:
            record["node"] = node.id
        if self.branch is not None:
            record["branch"] = self.branch
        if detail:
            record["detail"] = str(detail)[:2000]
        self.sink.append(record)

    # ── node execution + failure policy ──────────────────────────
    def _instance(self, node: NodeSpec):
        if node.primitive not in self._instances:
            self._instances[node.primitive] = self.loop.registry.primitive(node.primitive)
        return self._instances[node.primitive]

    def _run_node(self, node: NodeSpec) -> dict:
        shape = PRIMITIVES[node.primitive]
        if shape.budgeted:
            amount = node.budget if node.budget is not None else DEFAULT_NODE_BUDGET
            for ledger in self.ledgers:
                ledger.allocate(amount, who=node.id)
        instance = self._instance(node)
        state = NodeState(self, node)
        attempt = 0
        while True:
            self._emit("start", node)
            try:
                instance.run(state, node.config)
            except Exception as exc:
                self._emit("failure", node, detail=f"{type(exc).__name__}: {exc}")
                if node.on_failure == "retry" and attempt < node.retries:
                    attempt += 1
                    self._emit("retry", node, detail=f"attempt {attempt + 1} of {node.retries + 1}")
                    continue
                if node.on_failure == "skip":
                    self._emit("skipped", node, detail=str(exc))
                    return {}
                self._emit("aborted", node, detail=str(exc))
                raise
            outputs = state.outputs()
            self._emit("result", node, detail=(", ".join(sorted(outputs)) or "(no outputs)"))
            self._emit("done", node)
            return outputs

    # ── the deterministic walk ───────────────────────────────────
    def run(self):
        state = self.state
        if self.branch is None:
            if state.goal is None:
                raise GraphLoopError(
                    "graph needs the resolved goal (goal_resolver slot) before it runs"
                )
            state.add_goal()
            state.transition_to(AgentStatus.EXECUTING)

        graph = self.graph
        ids = graph.topo
        specs = [graph.node(n) for n in ids]
        index = {n: i for i, n in enumerate(ids)}

        i = 0
        while i < len(specs):
            node = specs[i]
            outputs = self._run_node(node)
            self.log.record(node.id, outputs)

            jumped = False
            for eidx in graph.control_out.get(node.id, ()):
                if _verdict_failed(outputs):
                    edge = graph.edges[eidx]
                    cap = edge.max_passes or 0
                    if self.taken.get(eidx, 0) < cap:
                        self.taken[eidx] = self.taken.get(eidx, 0) + 1
                        i = index[edge.target]
                        self._emit(
                            "control",
                            node,
                            detail=(
                                f"verdict not passed -> re-run from {edge.target!r} "
                                f"(pass {self.taken[eidx]}/{cap})"
                            ),
                        )
                        jumped = True
                break  # at most one control edge is taken, declared order
            if not jumped:
                i += 1

        return self._pick_answer()

    def _pick_answer(self):
        for _, outputs in reversed(self.log.entries):
            if outputs.get("result") is not None:
                return outputs["result"]
        for _, outputs in reversed(self.log.entries):
            if outputs.get("merged") is not None:
                return outputs["merged"]
        return ""

    # ── parallel branches (concurrent, isolated, bounded) ────────
    def run_branches(self, branches, max_parallel: int, context):
        n = len(branches)
        workers = max(1, min(int(max_parallel or DEFAULT_MAX_PARALLEL), n))
        outer_state = self.state

        def work(idx: int):
            b = branches[idx]
            label = b.name
            # Fresh blackboard per branch (per-agent memory invariant, extended
            # to branches): concurrent execution can never interleave commits.
            branch_state = AgentState(
                agent_id=f"{outer_state.agent_id}@{label}",
                goal=outer_state.goal,
                conversation=ConversationMemory(),
                metadata={},
            )
            ledgers = ([BudgetLedger(b.budget)] if b.budget is not None else []) + self.ledgers
            eng = _GraphEngine(
                self.loop,
                self.components,
                branch_state,
                b.graph,
                sink=self.sink,
                ledgers=ledgers,
                branch=label,
                seed={"context": context} if context else None,
            )
            return eng.run()

        if _loop_running():
            # Inside a running event loop (FastAPI async path): thread pool.
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="graph-branch") as pool:
                return list(pool.map(work, range(n)))
        # Sync context (REPL/tests): asyncio to keep collection order declared.
        return asyncio.run(self._async_map(work, n, workers))

    @staticmethod
    async def _async_map(work, n: int, workers: int):
        sem = asyncio.Semaphore(workers)

        async def one(idx: int):
            async with sem:
                return await asyncio.to_thread(work, idx)

        return list(await asyncio.gather(*(one(idx) for idx in range(n))))


class GraphLoop(AgentLoop):
    """Declarative loop topology: the active graph (JSON) IS the loop.

    Activate it like any loop alias — with a graph id attached:
        POST /api/components/activate  {"loop": "graph", "graph_id": "..."}
    The graph document itself travels through the ``/api/graphs`` endpoints
    (saved as a JSON file — the store).
    """

    name = "graph"
    version = "1.0.0"

    def __init__(self, registry=None, context=None, graph_store=None):
        self.registry = registry
        self.context = context
        self._store = graph_store

    def resolve_store(self):
        if self._store is not None:
            return self._store
        if self.context is not None:
            stored = (self.context.extras or {}).get("graph_store")
            if stored is not None:
                self._store = stored
                return stored
        return get_graph_store()

    def run(self, components: LoopComponents, state):
        if self.registry is None:
            raise GraphLoopError("the graph loop needs a ComponentRegistry (the primitives namespace)")
        store = self.resolve_store()
        graph_id = store.active_id
        if graph_id is None:
            raise GraphLoopError(
                "no active graph — save one (POST /api/graphs) then activate with "
                "{\"loop\": \"graph\", \"graph_id\": \"...\"}"
            )
        doc = store.get(graph_id)
        graph = validate_graph(doc)  # belt + braces: a stored doc must still run
        sink = EventSink(state)
        engine = _GraphEngine(
            self, components, state, graph, sink=sink, ledgers=[BudgetLedger(graph.budget)]
        )
        try:
            answer = engine.run()
        except Exception as exc:
            state.transition_to(AgentStatus.FAILED)
            store.record_run(graph_id, {"status": "failed", "error": str(exc), "events": sink.events()})
            raise
        if isinstance(answer, (list, tuple)):
            answer = "\n\n".join(str(a) for a in answer if a is not None)
        state.transition_to(AgentStatus.COMPLETED)
        store.record_run(graph_id, {"status": "ok", "answer": answer, "events": sink.events()})
        return answer
