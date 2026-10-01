/**
 * API client for the learning-ai-harness backend (designer surface).
 *
 * Endpoints (see app/server.py):
 *   GET    /api/components             — one door: slots, presets, primitives, graphs
 *   GET    /api/graphs                 — saved documents (active + list)
 *   POST   /api/graphs                 — save (validated; invalid = 400, never saved)
 *   DELETE /api/graphs/{id}            — delete a document
 *   GET    /api/graphs/{id}/last-run   — last run record: status, answer, node events
 *   POST   /api/components/activate    — {"loop": "graph", "graph_id": "..."}
 *   POST   /api/chat                   — one turn (stateless: full thread rides each call)
 *   GET    /health                     — liveness probe
 */

import {
  ApiError,
  type ComponentsStatus,
  type GraphDoc,
  type GraphsStatus,
  type LastRun,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handle<T>(res: Response, parse: (body: unknown) => T): Promise<T> {
  if (!res.ok) {
    let detail = "";
    try {
      const data = (await res.json()) as { detail?: unknown; message?: unknown };
      detail = String(data.detail ?? data.message ?? "").slice(0, 300);
    } catch {
      /* no body */
    }
    throw new ApiError(
      "http",
      detail ? `Backend ${res.status}: ${detail}` : `Backend error ${res.status}`,
      res.status
    );
  }
  const text = await res.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    throw new ApiError(
      "parse",
      `Backend returned a non-JSON response (${res.status}): ${text.slice(0, 200)}`
    );
  }
  try {
    return parse(body);
  } catch (err) {
    const why = err instanceof Error ? err.message : String(err);
    throw new ApiError(
      "parse",
      `Backend response didn't match the expected shape: ${why} — body: ${text.slice(0, 200)}`
    );
  }
}

function guardNetwork(err: unknown, fallback: string): never {
  if (err instanceof DOMException && err.name === "AbortError") throw err;
  throw new ApiError("network", fallback);
}

/** GET /api/components — the single discovery door (primitives + graphs). */
export async function getComponents(): Promise<ComponentsStatus> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/components`, { cache: "no-store" });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => b as ComponentsStatus);
}

/** GET /api/graphs — saved graph documents. */
export async function getGraphs(): Promise<GraphsStatus> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/graphs`, { cache: "no-store" });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => b as GraphsStatus);
}

/** POST /api/graphs — save (create/overwrite) by id; invalid = 400. */
export async function saveGraph(
  id: string,
  name: string,
  doc: GraphDoc
): Promise<GraphsStatus["graphs"][number]> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/graphs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, name, graph: doc }),
    });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => (b as { graphs: GraphsStatus["graphs"] }).graphs.find((g) => g.id === id) ?? (b as never));
}

/** GET /api/graphs/{id} — fetch one saved document (for the canvas). */
export async function getGraph(id: string): Promise<{ id: string; name: string; graph: GraphDoc }> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/graphs/${encodeURIComponent(id)}`, { cache: "no-store" });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => b as { id: string; name: string; graph: GraphDoc });
}

/** DELETE /api/graphs/{id}. */
export async function deleteGraph(id: string): Promise<GraphsStatus> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/graphs/${encodeURIComponent(id)}`, { method: "DELETE" });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => b as GraphsStatus);
}

/** GET /api/graphs/{id}/last-run — 404 until the graph has run here. */
export async function getLastRun(id: string): Promise<LastRun> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/graphs/${encodeURIComponent(id)}/last-run`, {
      cache: "no-store",
    });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => b as LastRun);
}

/** POST /api/components/activate — swap components in at runtime. */
export async function activate(body: {
  preset?: string;
  slot?: string;
  alias?: string;
  loop?: string;
  graph_id?: string;
}): Promise<ComponentsStatus> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/components/activate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => b as ComponentsStatus);
}

/** POST /api/chat — one turn; the harness is stateless, the thread rides in. */
export async function postChat(
  message: string,
  conversation: { role: "user" | "agent"; content: string }[] = [],
  signal?: AbortSignal
): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation }),
      signal,
    });
  } catch (err) {
    guardNetwork(err, "Could not reach the AI backend. Is it running?");
  }
  return handle(res, (b) => String((b as { answer?: string }).answer ?? "").trim() || "No response received.");
}

/** GET /health — the connection indicator. */
export async function isBackendOnline(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    if (!res.ok) return false;
    const data = (await res.json()) as { status?: string };
    return data.status === "ok";
  } catch {
    return false;
  }
}
