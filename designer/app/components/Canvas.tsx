"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./Canvas.module.css";
import NodeCard from "./NodeCard";
import {
  NODE_W,
  anchorY,
  controlAnchorY,
  edgeTypable,
  inputTypes,
  isControlSource,
  outputTypes,
  type CanvasEdge,
  type CanvasGraph,
  type CanvasNode,
  type PrimitiveMeta,
} from "../lib/graph";

export type Selection =
  | { kind: "node"; id: string }
  | { kind: "edge"; key: string };

interface Props {
  graph: CanvasGraph;
  meta: Map<string, PrimitiveMeta>;
  online: boolean;
  selection: Selection | null;
  onSelect: (sel: Selection | null) => void;
  onMoveNode: (id: string, x: number, y: number) => void;
  onRemoveNode: (id: string) => void;
  onAddEdge: (from: string, to: string, type: "data" | "control") => void;
  onRemoveEdge: (key: string) => void;
}

function edgeKey(e: CanvasEdge): string {
  return `${e.from}->${e.to}:${e.type}`;
}

function rowsOf(node: CanvasNode, meta: Map<string, PrimitiveMeta>): number {
  return Math.max(
    inputTypes(node.primitive, meta).length,
    outputTypes(node.primitive, meta).length,
    1
  );
}

function outAnchor(node: CanvasNode, meta: Map<string, PrimitiveMeta>, index: number): [number, number] {
  return [node.x + NODE_W, node.y + anchorY(index)];
}

function inAnchor(node: CanvasNode, index: number): [number, number] {
  return [node.x, node.y + anchorY(index)];
}

function bezier(x1: number, y1: number, x2: number, y2: number, flip = false): string {
  const dist = Math.max(Math.abs(x2 - x1) * 0.5, 48);
  if (!flip) return `M ${x1} ${y1} C ${x1 + dist} ${y1}, ${x2 - dist} ${y2}, ${x2} ${y2}`;
  return `M ${x2} ${y2} C ${x2 - dist} ${y2}, ${x1 + dist} ${y1}, ${x1} ${y1}`;
}

type Drag =
  | { kind: "node"; id: string; dx: number; dy: number }
  | { kind: "pan"; dx: number; dy: number };

interface ConnectState {
  from: string;
  type: "data" | "control";
  x: number;
  y: number;
}

/** The node canvas: pan/zoom viewport, positioned node cards, typed port
 *  wires (data solid, control dashed), drag-to-connect from outputs. */
export default function Canvas({
  graph,
  meta,
  online,
  selection,
  onSelect,
  onMoveNode,
  onRemoveNode,
  onAddEdge,
  onRemoveEdge,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [pan, setPan] = useState({ x: 50, y: 30 });
  const [zoom, setZoom] = useState(1);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [connect, setConnect] = useState<ConnectState | null>(null);

  const byId = useMemo(
    () => new Map(graph.nodes.map((n) => [n.id, n])),
    [graph.nodes]
  );

  const toContent = (clientX: number, clientY: number) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: (clientX - rect.left - pan.x) / zoom,
      y: (clientY - rect.top - pan.y) / zoom,
    };
  };

  // Global drag/connect listeners while an interaction is in flight.
  useEffect(() => {
    if (!drag && !connect) return;
    const move = (e: PointerEvent) => {
      if (drag?.kind === "node") {
        const p = toContent(e.clientX, e.clientY);
        onMoveNode(
          drag.id,
          Math.max(0, p.x - drag.dx),
          Math.max(0, p.y - drag.dy)
        );
      } else if (drag?.kind === "pan") {
        setPan({ x: e.clientX - drag.dx, y: e.clientY - drag.dy });
      }
      if (connect) {
        const p = toContent(e.clientX, e.clientY);
        setConnect((c) => (c ? { ...c, x: p.x, y: p.y } : c));
      }
    };
    const up = () => {
      setDrag(null);
      setConnect(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drag, connect, pan, zoom]);

  const startNodeDrag = (e: React.PointerEvent, node: CanvasNode) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const p = toContent(e.clientX, e.clientY);
    onSelect({ kind: "node", id: node.id });
    setDrag({ kind: "node", id: node.id, dx: p.x - node.x, dy: p.y - node.y });
  };

  const startPan = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    onSelect(null);
    setDrag({ kind: "pan", dx: e.clientX - pan.x, dy: e.clientY - pan.y });
  };

  const startConnect = (
    e: React.PointerEvent,
    node: CanvasNode,
    type: "data" | "control"
  ) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const p = toContent(e.clientX, e.clientY);
    setConnect({ from: node.id, type, x: p.x, y: p.y });
  };

  const dropOnNode = (_e: React.PointerEvent, node: CanvasNode) => {
    if (!connect) return;
    if (connect.from !== node.id) {
      onAddEdge(connect.from, node.id, connect.type);
    }
    setConnect(null);
    // NOTE: no e.stopPropagation() here. pointerup must keep bubbling to the
    // window-level `up` listener in the drag effect above — that handler is
    // what clears `drag`, so swallowing the event left node/pan drags stuck
    // to the cursor whenever the pointer was released over a node card.
  };

  // Wheel zoom (deltaY) + keyboard delete of the selection.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && Math.abs(e.deltaY) < 1) return;
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      setZoom((z) => Math.min(1.6, Math.max(0.5, z * factor)));
    };
    el.addEventListener("wheel", onWheel, { passive: true });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      )
        return;
      if ((e.key === "Delete" || e.key === "Backspace") && selection) {
        if (selection.kind === "node") onRemoveNode(selection.id);
        else onRemoveEdge(selection.key);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selection, onRemoveNode, onRemoveEdge]);

  // ── edges ────────────────────────────────────────────────────────────────

  const dataSiblings = useMemo(() => {
    const m = new Map<string, CanvasEdge[]>();
    for (const e of graph.edges) {
      if (e.type !== "data") continue;
      m.set(`${e.from}`, [...(m.get(e.from) ?? []), e]);
    }
    return m;
  }, [graph.edges]);

  const inSiblings = useMemo(() => {
    const m = new Map<string, CanvasEdge[]>();
    for (const e of graph.edges) {
      if (e.type !== "data") continue;
      m.set(`${e.to}`, [...(m.get(e.to) ?? []), e]);
    }
    return m;
  }, [graph.edges]);

  const edgeGeom = (edge: CanvasEdge) => {
    const f = byId.get(edge.from);
    const t = byId.get(edge.to);
    if (!f || !t) return null;
    let x1: number, y1: number;
    if (edge.type === "control") {
      x1 = f.x + NODE_W;
      y1 = f.y + controlAnchorY(rowsOf(f, meta));
    } else {
      const idx = (dataSiblings.get(edge.from) ?? []).indexOf(edge);
      [x1, y1] = outAnchor(f, meta, Math.max(0, idx));
    }
    const inIdx = (inSiblings.get(edge.to) ?? []).indexOf(edge);
    const [x2, y2] = inAnchor(t, Math.max(0, inIdx));
    const flip = x2 < x1 - 10;
    return {
      d: bezier(x1, y1, x2, y2, flip),
      mx: (x1 + x2) / 2,
      my: (y1 + y2) / 2,
      valid:
        edge.type === "control" ? isControlSource(f.primitive) : edgeTypable(f.primitive, t.primitive, meta),
    };
  };

  const connectGeom = () => {
    if (!connect) return null;
    const f = byId.get(connect.from);
    if (!f) return null;
    let x1: number, y1: number;
    if (connect.type === "control") {
      x1 = f.x + NODE_W;
      y1 = f.y + controlAnchorY(rowsOf(f, meta));
    } else {
      const outCount = (dataSiblings.get(connect.from) ?? []).length;
      [x1, y1] = outAnchor(f, meta, outCount);
    }
    return { d: bezier(x1, y1, connect.x, connect.y), x1, y1 };
  };

  const cg = connectGeom();

  return (
    <div
      ref={viewportRef}
      className={styles.viewport}
      onPointerDown={startPan}
      role="application"
      aria-label="Graph canvas"
    >
      <div
        className={styles.content}
        style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
      >
        <svg className={styles.wires} width={1} height={1} overflow="visible">
          {graph.edges.map((edge) => {
            const g = edgeGeom(edge);
            if (!g) return null;
            const key = edgeKey(edge);
            const selected = selection?.kind === "edge" && selection.key === key;
            return (
              <g key={key}>
                <path
                  d={g.d}
                  className={styles.hit}
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    onSelect({ kind: "edge", key });
                  }}
                />
                <path
                  d={g.d}
                  className={`${styles.wire} ${
                    edge.type === "control" ? styles.wireCtl : ""
                  } ${selected ? styles.wireSel : ""} ${g.valid ? "" : styles.wireBad}`}
                  fill="none"
                  pointerEvents="none"
                />
                {edge.type === "control" && (
                  <text
                    x={g.mx}
                    y={g.my - 6}
                    className={styles.wireLabel}
                    textAnchor="middle"
                    pointerEvents="none"
                  >
                    ≤{edge.max_passes ?? 1}
                  </text>
                )}
              </g>
            );
          })}
          {cg && (
            <path d={cg.d} className={styles.ghost} fill="none" pointerEvents="none" />
          )}
        </svg>

        {graph.nodes.map((node) => (
          <NodeCard
            key={node.id}
            node={node}
            meta={meta}
            selected={selection?.kind === "node" && selection.id === node.id}
            connectActive={connect !== null && connect.from !== node.id}
            onCardPointerDown={startNodeDrag}
            onOutPointerDown={startConnect}
            onInPointerUp={dropOnNode}
            onRemove={onRemoveNode}
          />
        ))}
      </div>

      {graph.nodes.length === 0 && (
        <div className={styles.empty}>
          <p>Compose a loop: add primitives, then drag from an output to an input.</p>
          <p className={styles.emptyHint}>
            goal is the graph input — nodes like <code>research</code> and{" "}
            <code>plan</code> don't need a wire for it.
          </p>
        </div>
      )}

      <div className={styles.zoomer}>
        <button type="button" onClick={() => setZoom((z) => Math.max(0.5, z / 1.15))} aria-label="Zoom out">
          −
        </button>
        <span className={styles.zoomPct}>{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom((z) => Math.min(1.6, z * 1.15))} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={() => setZoom(1)} className={styles.reset}>
          1:1
        </button>
      </div>

      {!online && (
        <div className={styles.offline}>
          offline — showing the local table; save/run need the backend
        </div>
      )}
    </div>
  );
}
