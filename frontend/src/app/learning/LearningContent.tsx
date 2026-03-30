"use client";

import { useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { LearningSection } from "@/lib/api";

// Lazy-load the overlay (it imports AudioContext-dependent hook)
const VoiceIntroOverlay = dynamic(() => import("@/components/learning/VoiceIntroOverlay"), {
  ssr: false,
});

/* ─── DATA ─────────────────────────────────────────────────── */

const humanLanguages = [
  { flag: "🇬🇧", name: "Английский", native: "English", level: "A1 – C2", popular: true, available: true },
  { flag: "🇩🇪", name: "Немецкий", native: "Deutsch", level: "A1 – B2", popular: false, available: true },
  { flag: "🇫🇷", name: "Французский", native: "Français", level: "A1 – B2", popular: false, available: false },
  { flag: "🇪🇸", name: "Испанский", native: "Español", level: "A1 – B1", popular: false, available: false },
  { flag: "🇨🇳", name: "Китайский", native: "普通话", level: "HSK 1–4", popular: false, available: false },
  { flag: "🇯🇵", name: "Японский", native: "日本語", level: "N5 – N3", popular: false, available: false },
];

const llmCourses = [
  {
    icon: "✍️",
    title: "Prompt Engineering",
    desc: "Пиши промпты как профессионал: zero-shot, few-shot, chain-of-thought",
    tag: "Основы",
    tagColor: "text-green-400 bg-green-900/30 border-green-700/40",
    available: true,
  },
  {
    icon: "🔗",
    title: "RAG & Knowledge Bases",
    desc: "Retrieval-Augmented Generation: подключай внешние базы знаний к LLM",
    tag: "Средний",
    tagColor: "text-yellow-400 bg-yellow-900/30 border-yellow-700/40",
    available: true,
  },
  {
    icon: "🤖",
    title: "AI Agents",
    desc: "Создавай автономных агентов с инструментами, памятью и планированием",
    tag: "Продвинутый",
    tagColor: "text-red-400 bg-red-900/30 border-red-700/40",
    available: false,
  },
  {
    icon: "🎯",
    title: "Fine-tuning",
    desc: "Обучай модели на своих данных: LoRA, QLoRA, RLHF",
    tag: "Продвинутый",
    tagColor: "text-red-400 bg-red-900/30 border-red-700/40",
    available: false,
  },
  {
    icon: "👁️",
    title: "Computer Vision",
    desc: "Работа с изображениями: CLIP, Stable Diffusion, мультимодальные модели",
    tag: "Средний",
    tagColor: "text-yellow-400 bg-yellow-900/30 border-yellow-700/40",
    available: false,
  },
  {
    icon: "📊",
    title: "NLP & Embeddings",
    desc: "Векторные базы данных, семантический поиск, классификация текста",
    tag: "Средний",
    tagColor: "text-yellow-400 bg-yellow-900/30 border-yellow-700/40",
    available: false,
  },
];

const programmingLangs = [
  {
    icon: "🐍",
    name: "Python",
    desc: "Бэкенд, ML, автоматизация",
    tracks: ["Django", "FastAPI", "NumPy", "PyTorch"],
    xp: 3200,
    available: true,
  },
  {
    icon: "⚡",
    name: "JavaScript / TypeScript",
    desc: "Фронтенд, Node.js, фуллстек",
    tracks: ["React", "Next.js", "Node.js", "Bun"],
    xp: 2800,
    available: true,
  },
  {
    icon: "🦀",
    name: "Rust",
    desc: "Системное программирование, производительность",
    tracks: ["Ownership", "Async", "WASM", "CLI"],
    xp: 4500,
    available: false,
  },
  {
    icon: "🐹",
    name: "Go",
    desc: "Микросервисы, высоконагруженные системы",
    tracks: ["Goroutines", "gRPC", "HTTP", "Docker"],
    xp: 3600,
    available: false,
  },
  {
    icon: "🗄️",
    name: "SQL",
    desc: "Базы данных, оптимизация запросов",
    tracks: ["PostgreSQL", "Индексы", "Joins", "Window fn"],
    xp: 2100,
    available: false,
  },
  {
    icon: "☕",
    name: "Java / Kotlin",
    desc: "Enterprise, Android, Spring Boot",
    tracks: ["Spring", "JVM", "Coroutines", "Android"],
    xp: 3900,
    available: false,
  },
];

/* ─── COMPONENTS ────────────────────────────────────────────── */

function SectionHeader({
  icon,
  title,
  subtitle,
  accentClass,
  onVoice,
}: {
  icon: string;
  title: string;
  subtitle: string;
  accentClass: string;
  onVoice: () => void;
}) {
  const gradientFrom = accentClass.includes("cyan")
    ? "from-cyan-600/60 via-cyan-400/20"
    : accentClass.includes("purple")
    ? "from-purple-600/60 via-purple-400/20"
    : "from-amber-600/60 via-amber-400/20";

  return (
    <div className="mb-6">
      <div className="flex items-start justify-between gap-2">
        <div className="text-4xl mb-3 drop-shadow-[0_0_12px_currentColor]">{icon}</div>
        <button
          onClick={onVoice}
          className={`mt-1 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest border rounded-lg px-2.5 py-1.5 transition-all ${
            accentClass.includes("cyan")
              ? "border-cyan-800/50 text-cyan-600 hover:border-cyan-500/60 hover:text-cyan-400 hover:bg-cyan-950/30"
              : accentClass.includes("purple")
              ? "border-purple-800/50 text-purple-600 hover:border-purple-500/60 hover:text-purple-400 hover:bg-purple-950/30"
              : "border-amber-800/50 text-amber-600 hover:border-amber-500/60 hover:text-amber-400 hover:bg-amber-950/30"
          }`}
          aria-label={`Голосовое введение: ${title}`}
        >
          <span>🎙️</span>
          <span>Рассказать</span>
        </button>
      </div>
      <h2 className={`font-cinzel text-xl font-bold uppercase tracking-widest mb-1 ${accentClass}`}>
        {title}
      </h2>
      <p className="text-gray-500 text-xs font-mono uppercase tracking-wide">{subtitle}</p>
      <div className={`mt-3 h-[1px] bg-gradient-to-r ${gradientFrom} to-transparent`} />
    </div>
  );
}

function ComingSoonBadge() {
  return (
    <span className="absolute top-3 right-3 text-[9px] font-mono uppercase tracking-widest bg-gray-900 border border-gray-700 text-gray-500 px-2 py-0.5 rounded-full">
      скоро
    </span>
  );
}

/* ─── CONTENT (client component) ───────────────────────────── */

export default function LearningContent() {
  const [activeSection, setActiveSection] = useState<LearningSection | null>(null);

  return (
    <main id="main-content" className="min-h-screen bg-gray-950 pt-8 pb-20">
      {/* Voice overlay */}
      {activeSection && (
        <VoiceIntroOverlay
          section={activeSection}
          onClose={() => setActiveSection(null)}
        />
      )}

      {/* Hero */}
      <section className="container mx-auto px-4 mb-12 text-center">
        <p className="text-xs font-mono uppercase tracking-[0.3em] text-amber-600/70 mb-3">
          Академия Гильдии
        </p>
        <h1 className="font-cinzel text-3xl sm:text-4xl xl:text-5xl font-bold text-white mb-4 leading-tight">
          <span className="text-amber-400 drop-shadow-[0_0_20px_rgba(251,191,36,0.4)]">Прокачай</span>{" "}
          свои навыки
        </h1>
        <p className="text-gray-400 max-w-xl mx-auto text-sm leading-relaxed">
          Три направления обучения — выбери своё и повышай уровень вместе с гильдией.
          Зарабатывай XP за пройденные модули.
        </p>
      </section>

      {/* 3-column grid */}
      <section className="container mx-auto px-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-0 lg:divide-x lg:divide-gray-800/60">

          {/* ── COLUMN 1: Разговорные языки ── */}
          <div className="px-0 lg:pr-8 pb-12 lg:pb-0">
            <SectionHeader
              icon="🌍"
              title="Разговорные языки"
              subtitle="Speak the world"
              accentClass="text-cyan-400"
              onVoice={() => setActiveSection("human-languages")}
            />

            <div className="flex flex-col gap-3">
              {humanLanguages.map((lang) => (
                <div
                  key={lang.name}
                  className={`relative flex items-center gap-4 rounded-xl border p-4 transition-all duration-300 ${
                    lang.available
                      ? "border-cyan-900/50 bg-cyan-950/20 hover:border-cyan-600/50 hover:bg-cyan-950/40 hover:shadow-[0_0_16px_rgba(34,211,238,0.08)] cursor-pointer group"
                      : "border-gray-800/60 bg-gray-900/10 opacity-60"
                  }`}
                >
                  {!lang.available && <ComingSoonBadge />}
                  <span className="text-3xl shrink-0 leading-none">{lang.flag}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-cinzel font-bold text-sm text-gray-100 group-hover:text-cyan-200 transition-colors">
                        {lang.name}
                      </span>
                      {lang.popular && (
                        <span className="text-[9px] font-mono uppercase bg-amber-900/40 border border-amber-700/40 text-amber-400 px-1.5 py-0.5 rounded-full">
                          топ
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 font-mono">{lang.native}</div>
                    <div className="text-[10px] text-cyan-700 font-mono mt-1 uppercase tracking-wide">
                      {lang.level}
                    </div>
                  </div>
                  {lang.available && (
                    <span className="shrink-0 text-[10px] font-mono uppercase tracking-widest text-cyan-500 group-hover:text-cyan-300 transition-colors">
                      Начать →
                    </span>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-xl border border-cyan-900/30 bg-cyan-950/10 p-4 text-center">
              <p className="text-xs text-gray-500 font-mono">
                Flashcards · Диалоги · Аудирование · AI-репетитор
              </p>
            </div>
          </div>

          {/* ── COLUMN 2: LLM / Нейросети ── */}
          <div className="px-0 lg:px-8 py-12 lg:py-0 border-t border-b border-gray-800/60 lg:border-t-0 lg:border-b-0">
            <SectionHeader
              icon="🧠"
              title="LLM & Нейросети"
              subtitle="Train your mind"
              accentClass="text-purple-400"
              onVoice={() => setActiveSection("llm-ai")}
            />

            <div className="flex flex-col gap-3">
              {llmCourses.map((course) => (
                <div
                  key={course.title}
                  className={`relative rounded-xl border p-4 transition-all duration-300 ${
                    course.available
                      ? "border-purple-900/50 bg-purple-950/20 hover:border-purple-600/50 hover:bg-purple-950/40 hover:shadow-[0_0_16px_rgba(168,85,247,0.08)] cursor-pointer group"
                      : "border-gray-800/60 bg-gray-900/10 opacity-60"
                  }`}
                >
                  {!course.available && <ComingSoonBadge />}
                  <div className="flex items-start gap-3">
                    <span className="text-2xl shrink-0 leading-none mt-0.5">{course.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-cinzel font-bold text-sm text-gray-100 group-hover:text-purple-200 transition-colors">
                          {course.title}
                        </span>
                        <span className={`text-[9px] font-mono uppercase border px-1.5 py-0.5 rounded-full ${course.tagColor}`}>
                          {course.tag}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 leading-relaxed">{course.desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-xl border border-purple-900/30 bg-purple-950/10 p-4 text-center">
              <p className="text-xs text-gray-500 font-mono">
                OpenAI · Anthropic · LangChain · HuggingFace · Ollama
              </p>
            </div>
          </div>

          {/* ── COLUMN 3: Языки программирования ── */}
          <div className="px-0 lg:pl-8 pt-12 lg:pt-0">
            <SectionHeader
              icon="💻"
              title="Программирование"
              subtitle="Code your future"
              accentClass="text-amber-400"
              onVoice={() => setActiveSection("programming")}
            />

            <div className="flex flex-col gap-3">
              {programmingLangs.map((lang) => (
                <div
                  key={lang.name}
                  className={`relative rounded-xl border p-4 transition-all duration-300 ${
                    lang.available
                      ? "border-amber-900/50 bg-amber-950/20 hover:border-amber-600/50 hover:bg-amber-950/40 hover:shadow-[0_0_16px_rgba(251,191,36,0.08)] cursor-pointer group"
                      : "border-gray-800/60 bg-gray-900/10 opacity-60"
                  }`}
                >
                  {!lang.available && <ComingSoonBadge />}
                  <div className="flex items-start gap-3">
                    <span className="text-2xl shrink-0 leading-none mt-0.5">{lang.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-cinzel font-bold text-sm text-gray-100 group-hover:text-amber-200 transition-colors">
                          {lang.name}
                        </span>
                        {lang.available && (
                          <span className="text-[9px] font-mono text-amber-700 shrink-0">
                            +{lang.xp.toLocaleString()} XP
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mb-2">{lang.desc}</p>
                      <div className="flex flex-wrap gap-1">
                        {lang.tracks.map((track) => (
                          <span
                            key={track}
                            className="text-[9px] font-mono bg-gray-900 border border-gray-800 text-gray-400 px-1.5 py-0.5 rounded"
                          >
                            {track}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-xl border border-amber-900/30 bg-amber-950/10 p-4 text-center">
              <p className="text-xs text-gray-500 font-mono">
                Задачи · Code review · Проекты · Менторство
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA bottom banner */}
      <section className="container mx-auto px-4 mt-16">
        <div className="rounded-2xl border border-amber-900/40 bg-gradient-to-br from-gray-900 via-gray-950 to-black p-8 text-center shadow-[0_0_40px_rgba(217,119,6,0.06)]">
          <p className="text-xs font-mono uppercase tracking-[0.3em] text-amber-600/70 mb-2">
            Ранний доступ
          </p>
          <h3 className="font-cinzel text-xl font-bold text-white mb-3">
            Хочешь попасть в бету?
          </h3>
          <p className="text-gray-400 text-sm mb-6 max-w-sm mx-auto">
            Первые участники получат эксклюзивные значки и двойной XP за все пройденные модули.
          </p>
          <Link
            href="/auth/register"
            className="inline-block bg-gradient-to-r from-amber-800 to-amber-950 hover:from-amber-700 hover:to-amber-900 text-white px-8 py-3 rounded font-cinzel font-bold uppercase tracking-widest text-xs transition-all border border-amber-600/50 shadow-[0_0_15px_rgba(217,119,6,0.2)] hover:shadow-[0_0_25px_rgba(217,119,6,0.4)]"
          >
            Зарегистрироваться →
          </Link>
        </div>
      </section>
    </main>
  );
}
