/**
 * Live-run derivation (the canvas half of the API + canvas seam).
 *
 * The backend's event vocabulary (components/graph_loop.py, frozen v0
 * contract: observability) is the source of truth; here we fold a prefix or
 * the full event list into per-node states so the canvas can highlight the
 * CURRENT node while a run is in flight (status "running" on /last-run)
 * and show the finished outcome afterwards.
 *
 * Event → state map (engine order per node):
 *   start → running      done → ok
 *   failure → failed     retry → running (attempt resumes)
 *   skipped → skipped    aborted → failed (fail-fast)
 *   result / control are informational (no state change): `result` is
 *   followed immediately by `done` on the same node, `control` is an
 *   edge-level event (named for its verdict source, already `ok`).
 *
 * Folding in order is what makes re-runs read correctly: a control-edge
 * re-run emits start again, which flips the node back to `running`.
 * Parallel branches simply leave several nodes at `running` at once —
 * which is exactly what the canvas should highlight.
 */
import type { RunEvent } from "./types";

export type NodeRunState = "running" | "ok" | "failed" | "skipped";

const STATE_BY_EVENT: Record<string, NodeRunState> = {
  start: "running",
  done: "ok",
  failure: "failed",
  retry: "running",
  skipped: "skipped",
  aborted: "failed",
};

/** Per-node run state derived from (possibly partial) run events. */
export function deriveNodeStates(events: RunEvent[] | null | undefined): Map<string, NodeRunState> {
  const states = new Map<string, NodeRunState>();
  if (!events) return states;
  for (const ev of events) {
    if (!ev || typeof ev !== "object" || !ev.node) continue;
    const state = STATE_BY_EVENT[ev.event];
    if (state) states.set(ev.node, state);
  }
  return states;
}

/** The node ids currently executing (for the canvas highlight). */
export function runningNodes(states: Map<string, NodeRunState> | null | undefined): string[] {
  if (!states) return [];
  return [...states.entries()]
    .filter(([, s]) => s === "running")
    .map(([id]) => id)
    .sort();
}
