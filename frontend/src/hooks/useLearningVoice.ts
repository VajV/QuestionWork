"use client";

import { useState, useRef, useCallback } from "react";
import { fetchLearningVoiceIntro, fetchLearningChat, getApiErrorMessage } from "@/lib/api";
import type { LearningSection, ChatMessage } from "@/lib/api";

export type VoiceState = "idle" | "loading" | "playing" | "error" | "done";

export interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface UseLearningVoiceReturn {
  state: VoiceState;
  error: string | null;
  isSending: boolean;
  messages: ChatEntry[];
  /** Live AnalyserNode — valid while state === "playing", null otherwise */
  analyserRef: React.MutableRefObject<AnalyserNode | null>;
  start: (section: LearningSection) => Promise<void>;
  sendMessage: (section: LearningSection, text: string) => Promise<void>;
  stop: () => void;
}

export function useLearningVoice(): UseLearningVoiceReturn {
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [messages, setMessages] = useState<ChatEntry[]>([]);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  // Conversation history for context (role + content pairs passed to backend)
  const historyRef = useRef<ChatMessage[]>([]);

  const _stopAudio = useCallback(() => {
    try { sourceRef.current?.stop(); } catch { /* already stopped */ }
    sourceRef.current?.disconnect();
    sourceRef.current = null;
    analyserRef.current?.disconnect();
    analyserRef.current = null;
    audioCtxRef.current?.close().catch(() => undefined);
    audioCtxRef.current = null;
  }, []);

  const stop = useCallback(() => {
    _stopAudio();
    setState("idle");
    setError(null);
  }, [_stopAudio]);

  /** Play an audio blob and return a promise that resolves when playback ends. */
  const _playBlob = useCallback(async (blob: Blob): Promise<void> => {
    _stopAudio();

    const arrayBuffer = await blob.arrayBuffer();
    const ctx = new AudioContext();
    audioCtxRef.current = ctx;

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    analyserRef.current = analyser;

    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(analyser);
    analyser.connect(ctx.destination);
    sourceRef.current = source;

    return new Promise<void>((resolve) => {
      source.onended = () => {
        analyserRef.current = null;
        resolve();
      };
      source.start();
      setState("playing");
    });
  }, [_stopAudio]);

  const start = useCallback(
    async (section: LearningSection) => {
      _stopAudio();
      setMessages([]);
      historyRef.current = [];
      setState("loading");
      setError(null);

      try {
        const blob = await fetchLearningVoiceIntro(section);
        await _playBlob(blob);
        setState("done");
      } catch (err) {
        const msg = getApiErrorMessage(err) ?? "Ошибка воспроизведения";
        setError(msg);
        setState("error");
        analyserRef.current = null;
      }
    },
    [_stopAudio, _playBlob],
  );

  const sendMessage = useCallback(
    async (section: LearningSection, text: string) => {
      if (isSending || !text.trim()) return;

      const userEntry: ChatEntry = { id: crypto.randomUUID(), role: "user", content: text.trim() };
      setMessages((prev) => [...prev, userEntry]);
      setIsSending(true);
      setError(null);

      try {
        const { audioBlob, text: replyText } = await fetchLearningChat(
          section,
          historyRef.current,
          text.trim(),
        );

        // Update conversation history for next turn
        historyRef.current = [
          ...historyRef.current,
          { role: "user" as const, content: text.trim() },
          { role: "assistant" as const, content: replyText },
        ].slice(-12); // keep last 12 turns

        const aiEntry: ChatEntry = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: replyText,
        };
        setMessages((prev) => [...prev, aiEntry]);

        // Stop any current playback then play the response
        _stopAudio();
        await _playBlob(audioBlob);
        setState("done");
      } catch (err) {
        const msg = getApiErrorMessage(err) ?? "Ошибка отправки сообщения";
        setError(msg);
        setState("error");
      } finally {
        setIsSending(false);
      }
    },
    [isSending, _stopAudio, _playBlob],
  );

  return { state, error, isSending, messages, analyserRef, start, sendMessage, stop };
}

