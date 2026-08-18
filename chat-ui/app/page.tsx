"use client";

import { useEffect, useRef } from "react";
import { useChat } from "@/hooks/useChat";
import MessageList from "@/components/MessageList";
import ChatInput from "@/components/ChatInput";
import styles from "./page.module.css";

export default function ChatPage() {
  const { messages, loading, sendMessage, clearMessages } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>🤖 AI Assistant</h1>
          <p className={styles.subtitle}>
            Powered by learning-ai-harness
          </p>
        </div>
        {messages.length > 0 && (
          <button
            className={styles.clearBtn}
            onClick={clearMessages}
            aria-label="Clear conversation"
          >
            Clear
          </button>
        )}
      </header>

      {/* Message list */}
      <MessageList messages={messages} loading={loading} />
      <div ref={bottomRef} />

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={loading} />
    </div>
  );
}
