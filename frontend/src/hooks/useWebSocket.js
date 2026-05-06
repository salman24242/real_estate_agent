import { useCallback, useEffect, useRef, useState } from "react";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000";

/**
 * useWebSocket — connects to /api/ws/chat/{sessionId}, auto-reconnects with
 * exponential backoff up to 5 times.
 *
 * @param {string} sessionId
 * @param {(msg: object) => void} onMessage
 */
export function useWebSocket(sessionId, onMessage) {
  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (!sessionId) return;
    const url = `${WS_BASE}/api/ws/chat/${sessionId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      retriesRef.current = 0;
      setIsConnected(true);
    };

    ws.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data);
        onMessage(parsed);
      } catch (e) {
        console.warn("Could not parse WS message:", ev.data);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (retriesRef.current < 5) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 16000);
        retriesRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      try { ws.close(); } catch {}
    };
  }, [sessionId, onMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const sendMessage = useCallback((text) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ message: text }));
      return true;
    }
    return false;
  }, []);

  return { isConnected, sendMessage };
}
