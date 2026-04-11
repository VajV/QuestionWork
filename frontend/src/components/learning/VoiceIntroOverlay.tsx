"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import AudioVisualizer from "./AudioVisualizer";
import { useLearningVoice } from "@/hooks/useLearningVoice";
import type { LearningSection } from "@/lib/api";

const SECTION_META: Record<
  LearningSection,
  { icon: string; title: string; subtitle: string; color: string; accentHex: string }
> = {
  "human-languages": {
    icon: "🌍",
    title: "Разговорные языки",
    subtitle: "Английский, Немецкий, Французский и другие",
    color: "text-cyan-400",
    accentHex: "#22d3ee",
  },
  "llm-ai": {
    icon: "🧠",
    title: "LLM & Нейросети",
    subtitle: "Prompt Engineering, RAG, Fine-tuning",
    color: "text-purple-400",
    accentHex: "#a855f7",
  },
  programming: {
    icon: "💻",
    title: "Программирование",
    subtitle: "Python, TypeScript, Rust и другие",
    color: "text-amber-400",
    accentHex: "#f59e0b",
  },
};

interface Props {
  section: LearningSection;
  onClose: () => void;
}

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  0: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionInstance {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export default function VoiceIntroOverlay({ section, onClose }: Props) {
  const meta = SECTION_META[section];
  const { state, error, isSending, messages, analyserRef, start, sendMessage, stop } =
    useLearningVoice();

  const [inputText, setInputText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const handleSendRef = useRef<() => void>(() => undefined);

  // Auto-start intro when overlay mounts
  useEffect(() => {
    start(section);
    return () => stop();
  }, [section, start, stop]);

  // Scroll chat to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleClose = useCallback(() => {
    recognitionRef.current?.stop();
    stop();
    onClose();
  }, [stop, onClose]);

  // Escape to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleClose]);

  const handleSend = useCallback(async () => {
    const text = inputText.trim();
    if (!text || isSending) return;
    setInputText("");
    await sendMessage(section, text);
    inputRef.current?.focus();
  }, [inputText, isSending, sendMessage, section]);

  // Keep ref fresh so SpeechRecognition onend can call it without stale closure
  handleSendRef.current = handleSend;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleVoiceInput = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    const speechWindow = window as SpeechRecognitionWindow;
    const SpeechRecognitionCtor =
      speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) return; // browser doesn't support speech recognition

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "ru-RU";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognitionRef.current = recognition;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join("");
      setInputText(transcript);
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
      // Focus input so user can review and press Enter, or auto-send
      setTimeout(() => {
        handleSendRef.current();
      }, 80);
    };

    recognition.onerror = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognition.start();
    setIsListening(true);
  }, [isListening]);

  const isPlaying = state === "playing";
  const isLoading = state === "loading";
  const isDone = state === "done";
  const isError = state === "error";
  // Input active once intro is done OR after first message, but not while intro plays
  const inputDisabled = isSending || isLoading || (isPlaying && messages.length === 0);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-gray-950"
      role="dialog"
      aria-modal="true"
      aria-label={`Голосовой гид: ${meta.title}`}
    >
      {/* ── TOP BANNER (full-width visualizer strip) ──────────────── */}
      <div
        className="relative w-full flex-shrink-0 overflow-hidden"
        style={{ height: "160px" }}
        aria-hidden="true"
      >
        {/* Full-width visualizer canvas */}
        <div className="absolute inset-0">
          <AudioVisualizer
            analyser={analyserRef.current}
            isPlaying={isPlaying || isSending}
            color={meta.accentHex}
          />
        </div>

        {/* Top → bottom gradient overlay */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `linear-gradient(to bottom, ${meta.accentHex}20 0%, transparent 50%, rgba(3,7,18,0.92) 100%)`,
          }}
        />

        {/* ← Back button */}
        <button
          onClick={handleClose}
          className="absolute top-4 left-4 z-10 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-mono text-gray-300 hover:text-white transition-colors"
          style={{
            background: "rgba(0,0,0,0.55)",
            border: "1px solid rgba(255,255,255,0.12)",
            backdropFilter: "blur(8px)",
          }}
          aria-label="Назад"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Назад
        </button>

        {/* Repeat button */}
        {(isDone || isError) && (
          <button
            onClick={() => start(section)}
            className="absolute top-4 right-4 z-10 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-mono text-gray-400 hover:text-gray-200 transition-colors"
            style={{
              background: "rgba(0,0,0,0.55)",
              border: "1px solid rgba(255,255,255,0.10)",
              backdropFilter: "blur(8px)",
            }}
          >
            ↺ Повторить
          </button>
        )}

        {/* Section identity — centred */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 z-10 pointer-events-none px-20">
          <span className="text-4xl leading-none drop-shadow-lg">{meta.icon}</span>
          <h2 className={`font-cinzel font-bold text-lg tracking-widest drop-shadow-lg ${meta.color}`}>
            {meta.title}
          </h2>
          <p className="text-[10px] font-mono uppercase tracking-widest text-gray-400 opacity-80">
            {meta.subtitle}
          </p>
        </div>

        {/* Status indicator at bottom of banner */}
        <div className="absolute bottom-3 left-0 right-0 flex items-center justify-center gap-2 z-10">
          {isLoading && (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-pulse" />
              <span className="text-[11px] font-mono text-gray-500">Подготавливаю…</span>
            </>
          )}
          {(isPlaying || isSending) && (
            <div className="flex items-end gap-[3px] h-4">
              {[0, 1, 2, 3, 4].map((i) => (
                <span
                  key={i}
                  className="w-1 rounded-full animate-bounce"
                  style={{
                    height: `${6 + i * 3}px`,
                    backgroundColor: meta.accentHex,
                    animationDelay: `${i * 0.1}s`,
                    animationDuration: "0.65s",
                  }}
                />
              ))}
              <span className="ml-2 text-[11px] font-mono" style={{ color: meta.accentHex }}>
                {isSending ? "Думаю…" : "Говорю…"}
              </span>
            </div>
          )}
          {isDone && !isSending && messages.length === 0 && (
            <span className="text-[11px] font-mono text-gray-500">Задайте вопрос ниже ↓</span>
          )}
          {isError && !isSending && (
            <span className="text-[11px] font-mono text-red-400">{error ?? "Ошибка"}</span>
          )}
        </div>
      </div>

      {/* ── CHAT AREA ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-2xl mx-auto w-full px-4 py-4 space-y-3">
          {/* Empty state */}
          {messages.length === 0 && (isDone || isError) && (
            <div className="flex flex-col items-center justify-center gap-4 pt-12 text-center">
              <span className="text-6xl opacity-15">{meta.icon}</span>
              <p className="text-sm font-mono text-gray-600">
                Гид готов. Задайте любой вопрос о разделе.
              </p>
            </div>
          )}

          {/* Message bubbles */}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              <div
                className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[11px]"
                style={{
                  background:
                    msg.role === "assistant"
                      ? `${meta.accentHex}33`
                      : "rgba(255,255,255,0.08)",
                  border: `1px solid ${
                    msg.role === "assistant"
                      ? `${meta.accentHex}55`
                      : "rgba(255,255,255,0.12)"
                  }`,
                }}
              >
                {msg.role === "assistant" ? meta.icon : "👤"}
              </div>
              <div
                className={`px-3 py-2 rounded-xl text-sm leading-relaxed max-w-[80%] ${
                  msg.role === "user"
                    ? "bg-white/8 text-gray-200 rounded-tr-sm"
                    : "text-gray-200 rounded-tl-sm"
                }`}
                style={
                  msg.role === "assistant"
                    ? {
                        background: `${meta.accentHex}12`,
                        border: `1px solid ${meta.accentHex}22`,
                      }
                    : undefined
                }
              >
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ── INPUT ROW ─────────────────────────────────────────────── */}
      <div
        className="flex-shrink-0 border-t"
        style={{ borderColor: `${meta.accentHex}22` }}
      >
        <div className="max-w-2xl mx-auto w-full flex items-center gap-2 px-4 py-3">
          {/* Mic button */}
          <button
            onClick={toggleVoiceInput}
            disabled={inputDisabled}
            title={isListening ? "Остановить запись" : "Голосовой ввод (ru)"}
            className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all disabled:opacity-30"
            style={{
              background: isListening ? `${meta.accentHex}30` : "rgba(255,255,255,0.05)",
              border: isListening
                ? `1px solid ${meta.accentHex}80`
                : "1px solid rgba(255,255,255,0.08)",
            }}
            aria-label={isListening ? "Остановить запись" : "Голосовой ввод"}
          >
            {isListening ? (
              <span
                className="w-3 h-3 rounded-sm animate-pulse"
                style={{ background: meta.accentHex }}
              />
            ) : (
              <svg className="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3zm0 2a1 1 0 0 0-1 1v6a1 1 0 0 0 2 0V5a1 1 0 0 0-1-1zm-7 7a1 1 0 0 1 1 1 6 6 0 0 0 12 0 1 1 0 0 1 2 0 8 8 0 0 1-7 7.938V21h2a1 1 0 0 1 0 2H9a1 1 0 0 1 0-2h2v-2.062A8 8 0 0 1 4 12a1 1 0 0 1 1-1z" />
              </svg>
            )}
          </button>

          {/* Text input */}
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
            placeholder={
              isLoading
                ? "Загружается…"
                : isListening
                ? "Слушаю…"
                : "Задайте вопрос о разделе…"
            }
            maxLength={500}
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 outline-none focus:border-white/20 transition-colors disabled:opacity-40"
            autoComplete="off"
            spellCheck={false}
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={inputDisabled || !inputText.trim()}
            className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all disabled:opacity-30"
            style={{
              background: `${meta.accentHex}22`,
              border: `1px solid ${meta.accentHex}44`,
            }}
            aria-label="Отправить"
          >
            {isSending ? (
              <span
                className="w-4 h-4 border-2 rounded-full animate-spin"
                style={{
                  borderColor: `${meta.accentHex}40`,
                  borderTopColor: meta.accentHex,
                }}
              />
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                style={{ color: meta.accentHex }}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

