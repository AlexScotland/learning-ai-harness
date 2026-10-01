"use client";

import styles from "./NodeCard.module.css";
import {
  NODE_W,
  inputTypes,
  isControlSource,
  outputTypes,
  rowTop,
  type CanvasNode,
  type PrimitiveMeta,
} from "../lib/graph";

interface Props {
  node: CanvasNode;
  meta: Map<string, PrimitiveMeta>;
  selected: boolean;
  connectActive: boolean;
  onCardPointerDown: (e: React.PointerEvent, node: CanvasNode) => void;
  onOutPointerDown: (
    e: React.PointerEvent,
    node: CanvasNode,
    kind: "data" | "control"
  ) => void;
  onInPointerUp: (e: React.PointerEvent, node: CanvasNode) => void;
  onRemove: (id: string) => void;
}

/** One graph node: typed input ports (left), typed output ports (right),
 *  a control (repeat) port for verdict nodes. Ports are drag handles. */
export default function NodeCard({
  node,
  meta,
  selected,
  connectActive,
  onCardPointerDown,
  onOutPointerDown,
  onInPointerUp,
  onRemove,
}: Props) {
  const inputs = inputTypes(node.primitive, meta);
  const outputs = outputTypes(node.primitive, meta);
  const control = isControlSource(node.primitive);
  const rows = Math.max(inputs.length, outputs.length, 1);

  const branchSummary =
    node.primitive === "parallel"
      ? `${node.branches.length} branch${node.branches.length === 1 ? "" : "es"}`
      : null;

  return (
    <div
      className={`${styles.node} ${selected ? styles.selected : ""}`}
      style={{ left: node.x, top: node.y, width: NODE_W }}
      data-node={node.id}
      onPointerUp={(e) => onInPointerUp(e, node)}
    >
      <header
        className={styles.head}
        onPointerDown={(e) => onCardPointerDown(e, node)}
      >
        <span className={styles.primitive}>{node.primitive}</span>
        <span className={styles.id}>{node.id}</span>
        <button
          type="button"
          className={styles.remove}
          aria-label={`Remove node ${node.id}`}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onRemove(node.id)}
        >
          ×
        </button>
      </header>

      <div className={styles.body}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className={styles.row} style={{ top: rowTop(i) }}>
            <div className={styles.cellL}>
              {i < inputs.length && (
                <span
                  className={`${styles.port} ${styles.portIn} ${
                    connectActive ? styles.dropTarget : ""
                  }`}
                  style={{ top: 3 }}
                  title={`input: ${inputs[i]}`}
                  onPointerUp={(e) => onInPointerUp(e, node)}
                >
                  <span className={styles.dot} />
                  {inputs[i]}
                </span>
              )}
            </div>
            <div className={styles.cellR}>
              {i < outputs.length && (
                <span
                  className={`${styles.port} ${styles.portOut}`}
                  style={{ top: 3 }}
                  title={`output: ${outputs[i]}`}
                  onPointerDown={(e) =>
                    onOutPointerDown(e, node, "data")
                  }
                >
                  {outputs[i]}
                  <span className={styles.dot} />
                </span>
              )}
            </div>
          </div>
        ))}
        {control && (
          <div
            className={styles.row}
            style={{ top: rowTop(rows) + 10 }}
          >
            <div className={styles.cellL} />
            <div className={styles.cellR}>
              <span
                className={`${styles.port} ${styles.portCtl}`}
                style={{ top: 4 }}
                title="control edge: declared repeat (max passes)"
                onPointerDown={(e) => onOutPointerDown(e, node, "control")}
              >
                ⟲ repeat
                <span className={`${styles.dot} ${styles.dotCtl}`} />
              </span>
            </div>
          </div>
        )}
      </div>

      {branchSummary && <footer className={styles.foot}>{branchSummary}</footer>}
    </div>
  );
}
