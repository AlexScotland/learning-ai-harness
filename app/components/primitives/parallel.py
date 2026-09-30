"""parallel — bounded fan-out over inline branch graphs (concurrent, isolated).

Contract (v0):
  requires:  'goal' (inherited by every branch), optional 'context'
  provides:  'merged' — list of branch answers in DECLARED branch order
  rules:     branches run concurrently (asyncio/thread pool, max_parallel cap);
             each branch gets a FRESH blackboard (fresh conversation store);
             side-effect nodes (act) are rejected inside branches at build time;
             only a declared 'merge' node afterwards commits branch output to the
             shared conversation, in declared order
"""
from .base import NodeBase, NodeConfigError


class ParallelNode(NodeBase):
    name = "parallel"
    provides = ("merged",)
    accepts = ("goal", "context")
    requires = ("goal",)
    description = "Runs inline branch graphs concurrently (fresh blackboard per branch)"

    def run(self, state, config):
        branches = state.branches
        if not branches:
            raise NodeConfigError("parallel node requires a non-empty 'branches' list")
        context = state.get_optional("context")
        results = state.run_branches(branches, state.max_parallel, context)
        state.out("merged", results)
