"use client";

import { useState } from "react";
import styles from "./Inspector.module.css";
import type {
  CanvasEdge,
  CanvasGraph,
  CanvasNode,
  CheckIssue,
  PrimitiveMeta,
} from "../lib/graph";
import type { Selection } from "./Canvas";
import type { BranchSpec } from "../lib/types";

interface Props {
  graph: CanvasGraph;
  meta: Map<string, PrimitiveMeta>;
  selection: Selection | null;
  issues: CheckIssue[];
  onGraph: (patch: Partial<Pick<CanvasGraph, "name" | "budget" | "max_parallel">>) => void;
  onNode: (id: string, patch: Partial<CanvasNode>) => void;
  onEdge: (edge: CanvasEdge, patch: Partial<CanvasEdge>) => void;
  onBranches: (id: string, branches: BranchSpec[]) => void;
}

export default function Inspector(props: Props) {
  const { graph, meta, selection } = props;
  const node =
    selection?.kind === "node"
      ? graph.nodes.find((n) => n.id === selection.id)
      : undefined;
  const edge =
    selection?.kind === "edge"
      ? graph.edges.find(
          (e) =>
            e.from + "->" + e.to + ":" + e.type === selection.key
        )
      : undefined;

  return (
    <aside className={styles.inspector}>
      <section className={styles.block}>
        <h2>Graph settings</h2>
        <label className={styles.field}>
          <span>Name</span>
          <input
            value={graph.name}
            onChange={(e) => props.onGraph({ name: e.target.value })}
            placeholder="my-loop"
          />
        </label>
        <div className={styles.pair}>
          <label className={styles.field}>
            <span>Budget</span>
            <input
              type="number"
              min={0}
              placeholder="∞"
              value={graph.budget ?? ""}
              onChange={(e) =>
                props.onGraph({
                  budget: e.target.value === "" ? null : Number(e.target.value),
                })
              }
            />
          </label>
          <label className={styles.field}>
            <span>max_parallel</span>
            <input
              type="number"
              min={1}
              placeholder="4"
              value={graph.max_parallel ?? ""}
              onChange={(e) =>
                props.onGraph({
                  max_parallel:
                    e.target.value === "" ? null : Number(e.target.value),
                })
              }
            />
          </label>
        </div>
        <p className={styles.hint}>
          Budgets are ceilings in executor units — the graph ceiling is
          binding. Empty = no ceiling (default parallel = 4).
        </p>
      </section>

      {node && (
        <NodePanel
          key={node.id}
          node={node}
          graph={graph}
          meta={meta}
          onNode={props.onNode}
          onBranches={props.onBranches}
        />
      )}
      {edge && (
        <EdgePanel
          key={edge.from + edge.to + edge.type}
          edge={edge}
          onEdge={props.onEdge}
        />
      )}

      <section className={styles.block}>
        <h2>Checks</h2>
        {props.issues.length === 0 ? (
          <p className={styles.ok}>
            Structural checks pass. The server validator is the final word
            (it checks typable edges, entry, cycles, branch rules).
          </p>
        ) : (
          <ul className={styles.issues}>
            {props.issues.map((i, k) => (
              <li
                key={k}
                className={i.severity === "error" ? styles.issueErr : styles.issueWarn}
              >
                {i.message}
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

// ── node panel ────────────────────────────────────────────────────────────

function NodePanel({
  node,
  graph,
  meta,
  onNode,
  onBranches,
}: {
  node: CanvasNode;
  graph: CanvasGraph;
  meta: Map<string, PrimitiveMeta>;
  onNode: (id: string, patch: Partial<CanvasNode>) => void;
  onBranches: (id: string, branches: BranchSpec[]) => void;
}) {
  const p = meta.get(node.primitive);
  const incoming = graph.edges.filter((e) => e.to === node.id).length;
  const outgoing = graph.edges.filter((e) => e.from === node.id).length;

  const [configText, setConfigText] = useState(() =>
    JSON.stringify(node.config ?? {}, null, 2)
  );
  const [configErr, setConfigErr] = useState<string | null>(null);

  const applyConfig = () => {
    try {
      const parsed = JSON.parse(configText) as unknown;
      if (
        typeof parsed !== "object" ||
        parsed === null ||
        Array.isArray(parsed)
      )
        throw new Error("config must be a JSON object");
      setConfigErr(null);
      onNode(node.id, { config: parsed as Record<string, unknown> });
    } catch (err) {
      setConfigErr(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <section className={styles.block}>
      <h2>
        Node <code>{node.id}</code>
      </h2>
      <div className={styles.meta}>
        <span className={styles.pill}>{node.primitive}</span>
        {node.budget != null && <span className={styles.pill}>budget {node.budget}</span>}
        {node.on_failure && <span className={styles.pill}>{node.on_failure}</span>}
        <span className={styles.pill}>{incoming} in · {outgoing} out</span>
      </div>

      <label className={styles.field}>
        <span>ID</span>
        <input
          value={node.id}
          onChange={(e) => onNode(node.id, { id: e.target.value.replace(/\s/g, "") })}
        />
      </label>

      <div className={styles.pair}>
        <label className={styles.field}>
          <span>Budget</span>
          <input
            type="number"
            min={0}
            placeholder="∞"
            value={node.budget ?? ""}
            onChange={(e) =>
              onNode(node.id, {
                budget: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </label>
        <label className={styles.field}>
          <span>on_failure</span>
          <select
            value={node.on_failure ?? "abort"}
            onChange={(e) => onNode(node.id, { on_failure: e.target.value })}
          >
            <option value="">abort (default)</option>            <option value="skip">skip</option>
            <option value="retry(1)">retry(1)</option>
            <option value="retry(2)">retry(2)</option>
            <option value="retry(3)">retry(3)</option>
            <option value="retry(5)">retry(5)</option>
          </select>
        </label>
      </div>

      <label className={styles.field}>
        <span>config {p ? <em>({p.requires.join(", ") || "no inputs"})</em> : null}</span>
        <textarea
          rows={4}
          spellCheck={false}
          className={styles.codearea}
          value={configText}
          onChange={(e) => setConfigText(e.target.value)}
        />
        {configErr ? (
          <span className={styles.err}>{configErr}</span>
        ) : null}
      </label>
      <button type="button" className={styles.apply} onClick={applyConfig}>
        Apply config
      </button>

      {node.primitive === "parallel" && (
        <BranchEditor
          node={node}
          onBranches={(b) => onBranches(node.id, b)}
        />
      )}
    </section>
  );
}

// ── branch editor (parallel only) ─────────────────────────────────────────

function BranchEditor({
  node,
  onBranches,
}: {
  node: CanvasNode;
  onBranches: (b: BranchSpec[]) => void;
}) {
  const branches = node.branches;
  const [text, setText] = useState(() => JSON.stringify(branches, null, 2));
  const [err, setErr] = useState<string | null>(null);

  const apply = () => {
    try {
      const parsed = JSON.parse(text);
      if (!Array.isArray(parsed) || parsed.length === 0)
        throw new Error("branches must be a non-empty array");
      for (const b of parsed) {
        if (!b?.name || !b?.graph?.nodes)
          throw new Error("each branch needs { name, graph: { nodes } }");
      }
      setErr(null);
      onBranches(parsed as BranchSpec[]);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    }
  };

  return (
    <div className={styles.branchbox}>
      <h3>Inline branches (JSON)</h3>
      <p className={styles.hint}>
        Each branch is a mini-graph run on a fresh blackboard;{" "}
        <code>act</code> is rejected inside branches.
      </p>
      <textarea
        rows={7}
        spellCheck={false}
        className={styles.codearea}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {err && <span className={styles.err}>{err}</span>}
      <button type="button" className={styles.apply} onClick={apply}>
        Apply branches
      </button>
    </div>
  );
}

// ── edge panel ────────────────────────────────────────────────────────────

function EdgePanel({
  edge,
  onEdge,
}: {
  edge: CanvasEdge;
  onEdge: (edge: CanvasEdge, patch: Partial<CanvasEdge>) => void;
}) {
  return (
    <section className={styles.block}>
      <h2>
        Edge <code>{edge.from} → {edge.to}</code>
      </h2>
      <div className={styles.meta}>
        <span className={styles.pill}>{edge.type}</span>
      </div>
      {edge.type === "control" && (
        <label className={styles.field}>
          <span>max_passes (declared repeat ceiling)</span>
          <input
            type="number"
            min={1}
            value={edge.max_passes ?? 2}
            onChange={(e) =>
              onEdge(edge, {
                max_passes: Math.max(1, Number(e.target.value) || 1),
              })
            }
          />
        </label>
      )}
      <p className={styles.hint}>
        Control edges repeat the downstream path; data edges are the acyclic
        backbone.
      </p>
    </section>
  );
}
