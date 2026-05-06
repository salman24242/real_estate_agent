const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function sendChatMessage(message, sessionId) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId || null }),
  });

  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  return res.json();
}

export async function resetSession(sessionId) {
  if (!sessionId) return;
  await fetch(`${API_BASE}/api/chat/${sessionId}`, { method: "DELETE" });
}
