"use client";

import { useChat } from "@/hooks/useChat";
import { useTheme } from "@/hooks/useTheme";
import ChatHeader from "@/components/ChatHeader";
import MessageList from "@/components/MessageList";
import RetryBar from "@/components/RetryBar";
import ChatInput from "@/components/ChatInput";
import styles from "./page.module.css";

export default function ChatPage() {
  const {
    messages,
    loading,
    error,
    online,
    sendMessage,
    stop,
    clearMessages,
    retryLast,
    clearError,
  } = useChat();
  const { theme, toggle } = useTheme();

  return (
    <div className={styles.page}>
      <ChatHeader
        online={online}
        canClear={messages.length > 0}
        theme={theme}
        onToggleTheme={toggle}
        onClear={clearMessages}
      />

      <MessageList messages={messages} loading={loading} />

      <RetryBar
        error={error}
        canRetry={!loading && messages.some((m) => m.role === "user")}
        onRetry={retryLast}
        onDismiss={clearError}
      />

      <ChatInput onSend={sendMessage} loading={loading} onStop={stop} />
    </div>
  );
}
