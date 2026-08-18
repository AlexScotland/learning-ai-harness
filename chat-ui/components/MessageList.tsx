import type { Message } from "@/hooks/useChat";
import styles from "./MessageList.module.css";

interface MessageListProps {
  messages: Message[];
  loading: boolean;
}

export default function MessageList({ messages, loading }: MessageListProps) {
  return (
    <div className={styles.container} role="log" aria-live="polite">
      {messages.length === 0 && !loading && (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>💬</span>
          <p>Start a conversation with the AI assistant.</p>
          <p className={styles.emptyHint}>
            Ask questions, request code, or explore topics.
          </p>
        </div>
      )}

      {messages.map((msg, i) => (
        <div
          key={i}
          className={`${styles.bubble} ${
            msg.role === "user" ? styles.user : styles.agent
          }`}
        >
          <span className={styles.role}>
            {msg.role === "user" ? "You" : "Assistant"}
          </span>
          <p className={styles.text}>{msg.content}</p>
        </div>
      ))}

      {loading && (
        <div className={`${styles.bubble} ${styles.agent} ${styles.thinking}`}>
          <span className={styles.role}>Assistant</span>
          <p className={styles.text}>
            <span className={styles.dots}>
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
          </p>
        </div>
      )}
    </div>
  );
}
