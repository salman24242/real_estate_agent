import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MessageBubble from "./MessageBubble.jsx";
import { useWebSocket } from "../hooks/useWebSocket.js";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder.js";
import { resetSession } from "../api/chat.js";
import { synthesizeSpeech, transcribeAudio } from "../api/voice.js";

const STORAGE_KEY = "re_session_id";
const TTS_STORAGE_KEY = "re_tts_enabled";

function getOrCreateSessionId() {
  let sid = sessionStorage.getItem(STORAGE_KEY);
  if (!sid) {
    sid =
      (crypto.randomUUID && crypto.randomUUID()) ||
      `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    sessionStorage.setItem(STORAGE_KEY, sid);
  }
  return sid;
}

export default function ChatWindow() {
  const [sessionId, setSessionId] = useState(getOrCreateSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(
    () => localStorage.getItem(TTS_STORAGE_KEY) === "1"
  );
  const scrollRef = useRef(null);
  const audioRef = useRef(null);
  const ttsEnabledRef = useRef(ttsEnabled);

  useEffect(() => {
    ttsEnabledRef.current = ttsEnabled;
    localStorage.setItem(TTS_STORAGE_KEY, ttsEnabled ? "1" : "0");
    if (!ttsEnabled && audioRef.current) {
      try {
        audioRef.current.pause();
      } catch {
        /* no-op */
      }
    }
  }, [ttsEnabled]);

  const playReply = useCallback(async (text) => {
    try {
      const url = await synthesizeSpeech(text);
      if (audioRef.current) {
        try {
          audioRef.current.pause();
        } catch {
          /* no-op */
        }
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => URL.revokeObjectURL(url);
      audio.onerror = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (err) {
      console.warn("TTS failed:", err);
    }
  }, []);

  const handleWsMessage = useMemo(
    () => (msg) => {
      if (msg.type === "reply") {
        setMessages((prev) => {
          const next = prev.filter((m) => !m.typing);
          return [
            ...next,
            { id: crypto.randomUUID(), role: "assistant", content: msg.content },
          ];
        });
        setIsSending(false);
        if (ttsEnabledRef.current && msg.content) {
          playReply(msg.content);
        }
      } else if (msg.type === "listings") {
        setMessages((prev) => {
          if (prev.length === 0) return prev;
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === "assistant" && !next[i].typing) {
              next[i] = { ...next[i], listings: msg.data || [] };
              break;
            }
          }
          return next;
        });
      } else if (msg.type === "error") {
        setMessages((prev) => {
          const next = prev.filter((m) => !m.typing);
          return [
            ...next,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `Error: ${msg.message}`,
            },
          ];
        });
        setIsSending(false);
      }
    },
    [playReply]
  );

  const { isConnected, sendMessage } = useWebSocket(sessionId, handleWsMessage);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = (overrideText) => {
    const text = (overrideText ?? input).trim();
    if (!text || isSending) return;
    const sent = sendMessage(text);
    if (!sent) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Not connected to the server. Retrying…",
        },
      ]);
      return;
    }
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: "typing", role: "assistant", content: "…thinking", typing: true },
    ]);
    setInput("");
    setIsSending(true);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReset = async () => {
    await resetSession(sessionId);
    sessionStorage.removeItem(STORAGE_KEY);
    const nextId = getOrCreateSessionId();
    setSessionId(nextId);
    setMessages([]);
  };

  const handleTranscribedAudio = useCallback(
    async (blob) => {
      setIsTranscribing(true);
      try {
        const transcript = await transcribeAudio(blob);
        if (transcript) {
          handleSend(transcript);
        }
      } catch (err) {
        console.warn("Transcription failed:", err);
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              "I couldn't transcribe that clip. Please try again or type your message.",
          },
        ]);
      } finally {
        setIsTranscribing(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sendMessage]
  );

  const recorder = useVoiceRecorder({
    onStop: handleTranscribedAudio,
    onError: (err) => {
      console.warn("Mic error:", err);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "I couldn't access your microphone. Please check browser permissions.",
        },
      ]);
    },
  });

  const micDisabled =
    !recorder.isSupported || isSending || isTranscribing || !isConnected;

  return (
    <div className="app">
      <div className="chat-pane">
        <div className="chat-header">
          <div>
            <h1>Real Estate Chat Agent</h1>
          </div>
          <div className="header-actions">
            <button
              className={`tts-btn ${ttsEnabled ? "active" : ""}`}
              onClick={() => setTtsEnabled((v) => !v)}
              title={ttsEnabled ? "Voice replies: on" : "Voice replies: off"}
              aria-label="Toggle voice replies"
            >
              {ttsEnabled ? "Voice on" : "Voice off"}
            </button>
            <button className="reset-btn" onClick={handleReset}>
              New chat
            </button>
          </div>
        </div>

        <div className="messages" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              <h2>Describe the home you're looking for</h2>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </div>

        <div className="input-bar">
          <button
            type="button"
            className={`mic-btn ${recorder.isRecording ? "recording" : ""}`}
            onClick={recorder.toggle}
            disabled={micDisabled}
            title={
              !recorder.isSupported
                ? "Microphone not supported in this browser"
                : recorder.isRecording
                ? "Stop recording"
                : "Start voice input"
            }
            aria-label="Voice input"
          >
            {recorder.isRecording ? "■" : "🎤"}
          </button>
          <input
            value={input}
            placeholder={
              recorder.isRecording
                ? "Listening…"
                : isTranscribing
                ? "Transcribing…"
                : "Tell me what you're looking for…"
            }
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={!isConnected || recorder.isRecording || isTranscribing}
          />
          <button
            disabled={!isConnected || isSending || !input.trim()}
            onClick={() => handleSend()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
