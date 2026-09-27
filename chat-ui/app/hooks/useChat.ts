"use client";

import { useState, useCallback, useRef, useEffect } from "react";

export interface Message {
  role: "user" | "agent";
  content: string;
  timestamp: number;
}

interface UseChatReturn {
  messages: Message[];
  loading: boolean;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  clearMessages: () => void;
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// The backend is stateless: the conversation is owned by the frontend and
// sent with every POST. The thread itself is persisted to localStorage so a
// page refresh (or restart) restores it — no server-side session, no DB.
const STORAGE_KEY = "learning-ai-harness.thread.v1";

function loadThread(): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m): m is Message =>
        m &&
        (m.role === "user" || m.role === "agent") &&
        typeof m.content === "string"
    );
  } catch {
    return [];
  }
}

function saveThread(messages: Message[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  } catch {
    // Storage full or blocked — the thread still works for this session.
  }
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>(loadThread);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Persist the thread on every change so it survives refresh/restart.
  useEffect(() => {
    saveThread(messages);
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      // Prior turns (everything already in the thread before this message).
      const prior: Message[] = messages;

      // Optimistic user message
      const userMsg: Message = {
        role: "user",
        content: trimmed,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setError(null);

      // Abort any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            conversation: prior.map(({ role, content }) => ({ role, content })),
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new Error(
            `Server responded ${res.status}${body ? `: ${body.slice(0, 200)}` : ""}`
          );
        }

        const data = await res.json();
        const answer: string =
          data.answer || data.response || data.message || "No response received.";

        const agentMsg: Message = {
          role: "agent",
          content: answer,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, agentMsg]);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const msg =
          err instanceof Error ? err.message : "Unknown error occurred";
        setError(msg);
        const errMsg: Message = {
          role: "agent",
          content: `⚠️ ${msg}`,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, errMsg]);
      } finally {
        setLoading(false);
      }
    },
    [loading, messages]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore storage errors
      }
    }
  }, []);

  return { messages, loading, error, sendMessage, clearMessages };
}
