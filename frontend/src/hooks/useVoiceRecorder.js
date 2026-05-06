import { useCallback, useEffect, useRef, useState } from "react";

/**
 * useVoiceRecorder - click to start, click to stop.
 *
 * onStop(blob) is called with the recorded audio blob (webm/opus when the
 * browser supports it). onError(err) fires for permission / device errors.
 */
export function useVoiceRecorder({ onStop, onError } = {}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isSupported, setIsSupported] = useState(true);

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      typeof window.MediaRecorder !== "undefined" &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function";
    setIsSupported(Boolean(supported));
  }, []);

  const cleanup = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const start = useCallback(async () => {
    if (!isSupported || isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const preferredTypes = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ];
      const mimeType = preferredTypes.find(
        (t) => window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(t)
      );

      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined
      );
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        cleanup();
        setIsRecording(false);
        if (onStop && blob.size > 0) onStop(blob);
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      cleanup();
      setIsRecording(false);
      if (onError) onError(err);
    }
  }, [isSupported, isRecording, cleanup, onStop, onError]);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop();
    } else {
      cleanup();
      setIsRecording(false);
    }
  }, [cleanup]);

  const toggle = useCallback(() => {
    if (isRecording) stop();
    else start();
  }, [isRecording, start, stop]);

  useEffect(() => cleanup, [cleanup]);

  return { isRecording, isSupported, start, stop, toggle };
}
