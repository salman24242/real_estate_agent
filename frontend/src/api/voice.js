const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function transcribeAudio(blob) {
  const form = new FormData();
  const name = blob.type && blob.type.includes("webm") ? "clip.webm" : "clip.audio";
  form.append("audio", blob, name);

  const res = await fetch(`${API_BASE}/voice/stt`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`STT failed (${res.status})`);
  }
  const data = await res.json();
  return (data && data.transcript) || "";
}

export async function synthesizeSpeech(text) {
  const res = await fetch(`${API_BASE}/voice/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error(`TTS failed (${res.status})`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
