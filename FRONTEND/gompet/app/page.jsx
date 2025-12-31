"use client";

import { useEffect, useRef, useState } from "react";

const DEFAULT_SOCKET_URL = "ws://localhost/ws/notifications/2/?token=";

export default function Home() {
  const socketRef = useRef(null);
  const [socketUrl, setSocketUrl] = useState(DEFAULT_SOCKET_URL);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("rozłączony");
  const [messages, setMessages] = useState([]);

  const appendMessage = (message) => {
    setMessages((prev) => [message, ...prev].slice(0, 20));
  };

  const connect = () => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    const url = `${socketUrl}${token}`;
    const ws = new WebSocket(url);
    socketRef.current = ws;

    setStatus("łączenie...");

    ws.addEventListener("open", () => {
      setStatus("połączony");
      appendMessage("✅ Połączono z WebSocket.");
    });

    ws.addEventListener("message", (event) => {
      appendMessage(`📩 ${event.data}`);
    });

    ws.addEventListener("close", () => {
      setStatus("rozłączony");
      appendMessage("⚠️ Połączenie zamknięte.");
    });

    ws.addEventListener("error", () => {
      setStatus("błąd");
      appendMessage("❌ Wystąpił błąd WebSocket.");
    });
  };

  const disconnect = () => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  };

  useEffect(() => () => disconnect(), []);

  return (
    <main style={{
      fontFamily: "system-ui, sans-serif",
      padding: "2rem",
      maxWidth: "720px",
      margin: "0 auto"
    }}>
      <h1>Test WebSocket - Gompet</h1>
      <p>Połącz się z: <code>{DEFAULT_SOCKET_URL}&lt;JWT&gt;</code></p>

      <label style={{ display: "block", marginTop: "1rem" }}>
        Adres WebSocket
        <input
          type="text"
          value={socketUrl}
          onChange={(event) => setSocketUrl(event.target.value)}
          placeholder="ws://localhost/ws/notifications/2/?token="
          style={{
            display: "block",
            width: "100%",
            padding: "0.5rem",
            marginTop: "0.5rem"
          }}
        />
      </label>

      <label style={{ display: "block", marginTop: "1rem" }}>
        Token JWT
        <input
          type="text"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="wklej JWT"
          style={{
            display: "block",
            width: "100%",
            padding: "0.5rem",
            marginTop: "0.5rem"
          }}
        />
      </label>

      <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
        <button type="button" onClick={connect}>
          Połącz
        </button>
        <button type="button" onClick={disconnect}>
          Rozłącz
        </button>
        <span>Status: <strong>{status}</strong></span>
      </div>

      <section style={{ marginTop: "1.5rem" }}>
        <h2>Ostatnie wiadomości</h2>
        {messages.length === 0 ? (
          <p>Brak wiadomości.</p>
        ) : (
          <ul>
            {messages.map((message, index) => (
              <li key={`${message}-${index}`}>{message}</li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
