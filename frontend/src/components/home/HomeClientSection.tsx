"use client";

import { useEffect, useState } from "react";
import { motion, type Variants } from "@/lib/motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import ClientProofStrip from "@/components/marketing/ClientProofStrip";
import ClientTrustGrid from "@/components/marketing/ClientTrustGrid";
import LiveTrustProof from "@/components/marketing/LiveTrustProof";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getUserProfile, PublicUserProfile, UserProfile } from "@/lib/api";
import { getXpDisplay } from "@/lib/xp";
import { trackAnalyticsEvent } from "@/lib/analytics";

const revealUp = {
  initial: { opacity: 0, y: 28 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.25 },
  transition: { duration: 0.55, ease: "easeOut" },
} as const;

const staggerGroup: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
    },
  },
};

const staggerItem: Variants = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
};

const clientPathCards = [
  {
    icon: "🧭",
    title: "Сформулировать задачу без хаоса",
    eyebrow: "Что именно можно нанять",
    accent: "from-amber-500/20 via-amber-500/8 to-transparent",
    text: "Через QuestionWork можно закрывать FastAPI backend, Next.js dashboards, интеграции, срочные багфиксы и продуктовые MVP-спринты без разрозненных переписок.",
    bullets: ["Backend и API", "Frontend и dashboards", "Срочные исправления и audits"],
  },
  {
    icon: "🛡️",
    title: "Снизить риск до старта",
    eyebrow: "Почему клиенту спокойнее",
    accent: "from-sky-500/20 via-sky-500/8 to-transparent",
    text: "Платформа ведёт клиента через понятный контрактный поток: бриф, отбор, безопасная оплата, контроль сроков и подтверждённая сдача вместо хаотичного фриланс-рынка.",
    bullets: ["Структурированный процесс", "Прозрачные статусы", "Escrow и спорные кейсы"],
  },
  {
    icon: "🚀",
    title: "Быстро перейти к следующему шагу",
    eyebrow: "Что делать дальше",
    accent: "from-violet-500/20 via-violet-500/8 to-transparent",
    text: "Если задача ещё не оформлена, клиент идёт по отдельному маршруту для заказчиков. Если уже понимает стек и роль, сразу переходит к специалистам и квестам.",
    bullets: ["Маршрут для заказчиков", "Витрина специалистов", "Подготовка к публикации квеста"],
  },
];

const featuredQuests = [
  {
    title: "Refactor the Dragon API Gateway",
    reward: "$1,400",
    xp: 520,
    level: "Middle+",
    urgency: "Срочно",
    stack: ["FastAPI", "PostgreSQL", "Redis"],
    flavor: "Нужно усмирить старый gateway, закрыть узкие места по latency и привести логирование к боевому виду.",
  },
  {
    title: "Forge the Frontline Dashboard",
    reward: "$980",
    xp: 370,
    level: "Junior-Middle",
    urgency: "3 дня",
    stack: ["Next.js", "TypeScript", "Framer Motion"],
    flavor: "Собрать интерфейс для операционной панели с выразительным UX и адекватной адаптивностью.",
  },
  {
    title: "Tame the Payment Familiar",
    reward: "$1,900",
    xp: 610,
    level: "Senior",
    urgency: "Высокий приоритет",
    stack: ["Security", "Decimal", "Audit Trail"],
    flavor: "Исправить денежный поток и гарантировать предсказуемость транзакций без утечек и расхождений.",
  },
  {
    title: "Build the Whisper Network",
    reward: "$760",
    xp: 290,
    level: "Junior+",
    urgency: "Открыт набор",
    stack: ["WebSocket", "Notifications", "UX"],
    flavor: "Довести сообщения и уведомления до ощущения живой гильдии, а не сухого служебного модуля.",
  },
];

const guildEvents = [
  { icon: "✨", title: "AstraByte поднял уровень до 14", meta: "2 минуты назад", tone: "text-amber-300" },
  { icon: "📜", title: "Новый контракт опубликован в разделе Backend", meta: "8 минут назад", tone: "text-sky-300" },
  { icon: "🏆", title: "RuneMason завершил квест и получил отзыв 5★", meta: "14 минут назад", tone: "text-emerald-300" },
  { icon: "🔮", title: "CipherFox открыл редкий перк переговорщика", meta: "21 минуту назад", tone: "text-violet-300" },
];

const clientFocusSignals = [
  { label: "Стек и роли", value: "FastAPI • Next.js", note: "backend, dashboards, integrations, product delivery" },
  { label: "Операционный контур", value: "Бриф -> отбор -> сдача", note: "процесс понятен клиенту ещё до регистрации" },
  { label: "Контроль риска", value: "Escrow и dispute path", note: "безопасность сделки важнее декоративной RPG-оболочки" },
];

const clientDecisionPoints = [
  {
    title: "Что можно нанять",
    text: "Команды и специалисты под backend, frontend, интеграции, аналитические панели и срочные починки.",
  },
  {
    title: "Почему это безопаснее",
    text: "Процесс не начинается с хаоса: есть понятный маршрут, прозрачные статусы и управляемый контрактный поток.",
  },
  {
    title: "Куда идти дальше",
    text: "Открыть маршрут для заказчиков, посмотреть специалистов или подготовиться к публикации первого квеста.",
  },
];

const hiringEntryLinks = [
  { href: "/hire/fastapi-backend", label: "FastAPI backend" },
  { href: "/hire/nextjs-dashboard", label: "Next.js dashboard" },
  { href: "/hire/urgent-bugfix", label: "Urgent bugfix" },
  { href: "/hire/mvp-sprint", label: "MVP sprint" },
];

function SectionHeading({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">{eyebrow}</p>
      <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">{title}</h2>
      <p className="mt-4 text-sm leading-7 text-stone-400 sm:text-base">{text}</p>
    </div>
  );
}

function PublicGuildHub() {
  return (
    <main id="main-content" className="guild-hub-bg min-h-screen text-stone-100">
      <Header />

      <div className="guild-ambient pointer-events-none">
        <div className="guild-orb guild-orb-left" />
        <div className="guild-orb guild-orb-right" />
        <div className="guild-gridlines" />
      </div>

      <section className="relative overflow-hidden border-b border-white/6">
        <div className="container relative mx-auto px-4 py-10 sm:py-14 lg:py-20">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, ease: "easeOut" }}
            className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center"
          >
            <div className="relative z-10">
              <div className="guild-chip mb-5 inline-flex">Найм IT-специалистов с маршрутом для заказчика</div>
              <h1 className="max-w-4xl font-cinzel text-5xl font-bold leading-[0.95] text-stone-100 sm:text-6xl lg:text-7xl">
                Наймите IT-исполнителя без
                <span className="block bg-gradient-to-r from-amber-300 via-stone-100 to-sky-300 bg-clip-text text-transparent">
                  хаоса в откликах и переписках
                </span>
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-stone-300 sm:text-lg">
                QuestionWork помогает клиенту быстро собрать контракт на backend, frontend или срочную доработку:
                описать задачу, понять рамки сделки, выбрать исполнителя и довести работу до подтверждённой сдачи.
              </p>

              <div className="mt-6 flex flex-wrap gap-2 text-xs uppercase tracking-[0.24em] text-stone-400 sm:text-sm">
                <span className="guild-chip bg-white/[0.04] text-stone-200">FastAPI и API</span>
                <span className="guild-chip bg-white/[0.04] text-stone-200">Next.js и dashboards</span>
                <span className="guild-chip bg-white/[0.04] text-stone-200">Urgent bugfix и audit</span>
              </div>

              <div className="mt-6 flex flex-wrap gap-3 text-sm text-stone-300">
                {hiringEntryLinks.map((item) => (
                  <Button key={item.href} href={item.href} variant="ghost" className="rounded-full border border-white/10 px-4 py-2 normal-case tracking-normal text-stone-300 hover:border-amber-500/40 hover:text-amber-200">
                    {item.label}
                  </Button>
                ))}
              </div>

              <div className="mt-8 flex flex-col gap-4 sm:flex-row">
                <Button href="/for-clients" variant="primary" className="px-8 py-4 text-sm sm:text-base">
                  Маршрут для заказчиков
                </Button>
                <Button href="/marketplace" variant="secondary" className="px-8 py-4 text-sm sm:text-base border-stone-600/60 bg-black/30">
                  Посмотреть специалистов
                </Button>
              </div>

              <div className="mt-8 grid gap-4 lg:grid-cols-3">
                {clientDecisionPoints.map((item) => (
                  <div key={item.title} className="rounded-2xl border border-white/10 bg-black/25 p-4">
                    <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">{item.title}</p>
                    <p className="mt-3 text-sm leading-6 text-stone-300">{item.text}</p>
                  </div>
                ))}
              </div>

              <div className="mt-8 grid gap-4 sm:grid-cols-3">
                {clientFocusSignals.map((signal) => (
                  <div key={signal.label} className="guild-stat-panel">
                    <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">{signal.label}</p>
                    <div className="mt-3 font-cinzel text-3xl text-amber-300">{signal.value}</div>
                    <p className="mt-2 text-sm text-stone-400">{signal.note}</p>
                  </div>
                ))}
              </div>

              {process.env.NODE_ENV === "development" && (
                <div className="mt-8 max-w-md rounded-2xl border border-amber-700/20 bg-black/35 px-5 py-4 shadow-[inset_0_0_30px_rgba(0,0,0,0.3)]">
                  <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Dev Fast Entry</p>
                  <p className="mt-2 font-mono text-sm text-amber-300">novice_dev / password123</p>
                </div>
              )}
            </div>

            <div className="relative">
              <div className="guild-stage-frame">
                <div className="guild-stage-sheen" />
                <div className="guild-stage-panel">
                  <div className="flex items-center justify-between border-b border-white/10 pb-4">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Client Control</p>
                      <h3 className="mt-2 font-cinzel text-2xl text-stone-100">Понять рынок до старта</h3>
                    </div>
                    <div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.28em] text-emerald-300">
                      Contract path visible
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 sm:grid-cols-2">
                    <div className="parchment-card min-h-[132px]">
                      <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-amber-700">Что клиент видит сразу</p>
                      <h4 className="mt-3 font-cinzel text-xl text-stone-900">Стек, рамки и следующий шаг</h4>
                      <p className="mt-2 text-sm leading-6 text-stone-700">На первой же странице клиенту должно быть понятно, кого можно нанять, почему поток безопаснее и куда перейти дальше.</p>
                    </div>
                    <div className="guild-command-card">
                      <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-sky-300/80">Почему это спокойнее</p>
                      <ul className="mt-4 space-y-3 text-sm text-stone-300">
                        <li>Путь заказчика отделён от RPG-шума</li>
                        <li>Есть понятный контрактный сценарий</li>
                        <li>Следующий CTA не нужно угадывать</li>
                      </ul>
                    </div>
                  </div>

                  <div className="mt-5 rounded-2xl border border-white/10 bg-black/25 p-4">
                    <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Client flow at a glance</p>
                    <div className="mt-4 space-y-3">
                      {[
                        {
                          title: "1. Зафиксировать запрос",
                          text: "Оставить вводный lead или перейти к оформлению квеста, если задача уже понятна.",
                        },
                        {
                          title: "2. Сверить стек и рамки",
                          text: "Понять, кого именно искать: backend, dashboard, urgent fix или MVP delivery block.",
                        },
                        {
                          title: "3. Дойти до безопасной сдачи",
                          text: "Двигаться по contract path с видимыми статусами, escrow и dispute summary.",
                        },
                      ].map((item) => (
                        <div key={item.title} className="rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3">
                          <p className="font-cinzel text-sm text-stone-100">{item.title}</p>
                          <p className="mt-2 text-sm leading-6 text-stone-400">{item.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <motion.div {...revealUp}>
          <SectionHeading
            eyebrow="Путь заказчика"
            title="Сначала ясность для клиента, потом атмосфера мира"
            text="Buyer-facing путь должен объяснять три вещи без догадок: какие задачи здесь закрывают, почему процесс безопаснее типовой биржи и какой следующий шаг нужен прямо сейчас."
          />
        </motion.div>

        <motion.div
          variants={staggerGroup}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.2 }}
          className="mt-10 grid gap-6 lg:grid-cols-3"
        >
          {clientPathCards.map((role) => (
            <motion.div key={role.title} variants={staggerItem}>
              <Card className="role-card h-full overflow-hidden border-white/10 bg-gradient-to-b from-white/[0.05] to-black/30 p-0" hover>
                <div className={`h-1 w-full bg-gradient-to-r ${role.accent}`} />
                <div className="p-7">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-stone-500">{role.eyebrow}</p>
                      <h3 className="mt-3 font-cinzel text-2xl text-stone-100">{role.title}</h3>
                    </div>
                    <div className="text-4xl">{role.icon}</div>
                  </div>
                  <p className="mt-5 text-sm leading-7 text-stone-400">{role.text}</p>
                  <div className="mt-6 flex flex-wrap gap-2">
                    {role.bullets.map((bullet) => (
                      <span key={bullet} className="guild-chip bg-white/[0.04] text-stone-300">
                        {bullet}
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </section>

      <section className="border-y border-white/6 bg-black/18">
        <div className="container mx-auto px-4 py-20">
          <motion.div {...revealUp} className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <SectionHeading
              eyebrow="Доказательства вместо вымысла"
              title="Trust layer должен опираться на live data и понятный процесс"
              text="Публичная страница спроса не должна продавать рынок через вымышленные квесты, несуществующих лидеров недели и декоративную активность. Здесь остаются только честные сигналы и объяснение механики сделки."
            />
            <Button href="/quests" variant="secondary" className="self-start border-stone-600/60 bg-black/20 px-6 py-3 text-sm">
              Открыть все квесты
            </Button>
          </motion.div>

          <LiveTrustProof className="mt-10" />
          <ClientProofStrip className="mt-10" />
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <ClientTrustGrid />
      </section>

      <section className="container mx-auto px-4 pb-20">
        <motion.div {...revealUp} className="cta-banner">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Готов к вступлению?</p>
            <h2 className="mt-3 max-w-2xl font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">
              Собери репутацию, возьми первый контракт и преврати профиль в легенду гильдии.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-300 sm:text-base">
              Внутри уже есть рынок задач, RPG-прогрессия, отзывы, сообщения и ощущение мира. Осталось зайти и начать путь.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button href="/auth/register" variant="rpg-special" className="px-8 py-4">
              Создать персонажа
            </Button>
            <Button href="/auth/login" variant="ghost" className="border-stone-600/40 px-8 py-4 text-stone-300 hover:text-white">
              Вернуться в зал
            </Button>
          </div>
        </motion.div>
      </section>
    </main>
  );
}

function AuthenticatedGuildHome({ profile }: { profile: PublicUserProfile }) {
  const xpDisplay = getXpDisplay(profile.xp, profile.xp_to_next);
  const currentFocus = featuredQuests.slice(0, 2);

  return (
    <main id="main-content" className="guild-hub-bg min-h-screen text-stone-100">
      <Header />

      <div className="container mx-auto px-4 py-8 sm:py-10 lg:py-14">
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="grid items-start gap-8 xl:grid-cols-[1.15fr_0.85fr]"
        >
          <Card className="overflow-hidden border-white/10 bg-gradient-to-br from-stone-950/90 via-slate-950/90 to-black p-0 shadow-[0_30px_80px_rgba(0,0,0,0.4)]">
            <div className="relative p-8 sm:p-10">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.18),transparent_36%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.12),transparent_30%)]" />
              <div className="relative flex flex-col gap-8 lg:flex-row lg:items-start">
                <div className="relative shrink-0">
                  <div className="avatar-frame flex h-32 w-32 items-center justify-center bg-black/60 text-4xl font-cinzel font-bold text-amber-300">
                    {profile.username[0].toUpperCase()}
                  </div>
                  <div className="absolute -bottom-4 left-1/2 -translate-x-1/2">
                    <LevelBadge level={profile.level} grade={profile.grade} />
                  </div>
                </div>

                <div className="flex-1 pt-4 lg:pt-0">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Свиток героя</p>
                      <h1 className="mt-2 font-cinzel text-4xl font-bold text-stone-100">{profile.username}</h1>
                    </div>
                    <span className="guild-chip self-start bg-white/[0.05] text-stone-300">{profile.character_class || "Класс не выбран"}</span>
                  </div>

                  <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-300">
                    Добро пожаловать обратно в зал гильдии. Здесь видно твой прогресс, ближайшие цели и квесты,
                    которые сейчас лучше всего подходят под текущий ранг и темп роста.
                  </p>

                  <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Прогресс текущего ранга</p>
                      <p className="font-mono text-sm text-amber-300">{xpDisplay.label}</p>
                    </div>
                    <div className="mt-3 xp-bar-track h-3">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${xpDisplay.percent}%` }}
                        transition={{ duration: 1.2, ease: "easeOut", delay: 0.15 }}
                        className="xp-bar-fill relative"
                      >
                        <div className="absolute inset-y-0 right-0 w-10 bg-gradient-to-r from-transparent to-white/25" />
                      </motion.div>
                    </div>
                  </div>

                  <div className="mt-6 grid max-w-3xl gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <Button href="/quests" variant="primary" className="w-full px-7 py-3.5">Взять новый квест</Button>
                    <Button href="/profile" variant="secondary" className="w-full border-stone-600/60 bg-black/20 px-7 py-3.5">Открыть профиль</Button>
                    <Button href="/profile/class" variant="secondary" className="w-full border-stone-600/60 bg-black/20 px-7 py-3.5">Перки и класс</Button>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Card className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-8">
            <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-sky-300/80">Пульс гильдии</p>
            <div className="mt-6 space-y-4">
              {guildEvents.map((event) => (
                <div key={event.title} className="activity-row">
                  <div className="activity-icon">{event.icon}</div>
                  <div className="flex-1">
                    <p className={`text-sm font-medium ${event.tone}`}>{event.title}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-500">{event.meta}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </motion.section>

        <motion.section
          {...revealUp}
          className="mt-8 grid gap-4 md:grid-cols-3"
        >
          {clientFocusSignals.map((signal) => (
            <Card
              key={signal.label}
              className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-6"
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">{signal.label}</p>
              <p className="mt-3 font-cinzel text-3xl text-amber-300">{signal.value}</p>
              <p className="mt-2 text-sm text-stone-400">{signal.note}</p>
            </Card>
          ))}
        </motion.section>

        <motion.section {...revealUp} className="mt-10 grid gap-8 xl:grid-cols-[0.9fr_1.1fr]">
          <StatsPanel stats={profile.stats} reputationStats={profile.reputation_stats} />

          <Card className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Подходящие квесты</p>
                <h2 className="mt-2 font-cinzel text-3xl text-stone-100">Лучшие цели на этот заход</h2>
              </div>
              <Button href="/quests" variant="secondary" className="border-stone-600/60 bg-black/20 px-5 py-3 text-xs">Все квесты</Button>
            </div>

            <div className="mt-6 space-y-4">
              {currentFocus.map((quest) => (
                <div key={quest.title} className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap gap-2">
                        <span className="guild-chip bg-amber-500/10 text-amber-300">{quest.level}</span>
                        <span className="guild-chip bg-sky-500/10 text-sky-300">{quest.urgency}</span>
                      </div>
                      <h3 className="mt-3 font-cinzel text-xl text-stone-100">{quest.title}</h3>
                      <p className="mt-3 text-sm leading-7 text-stone-400">{quest.flavor}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-right">
                      <p className="font-cinzel text-2xl text-amber-300">{quest.reward}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.22em] text-stone-500">{quest.xp} XP</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </motion.section>
      </div>
    </main>
  );
}

export default function HomeClientSection() {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<PublicUserProfile | UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    trackAnalyticsEvent("landing_view");
  }, []);

  useEffect(() => {
    async function loadProfile() {
      if (!isAuthenticated || !user?.id) {
        setLoading(false);
        return;
      }

      try {
        const data = await getUserProfile(user.id);
        setProfile(data);
      } catch (e) {
        console.warn("Failed to load profile, using auth context fallback", e);
        setProfile(user);
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [isAuthenticated, user]);

  if (authLoading) {
    return (
      <main className="guild-hub-bg flex min-h-screen items-center justify-center text-stone-100">
        <div className="text-center">
          <div className="mx-auto mb-4 h-16 w-16 rounded-full border-4 border-amber-400/70 border-t-transparent animate-spin" />
          <p className="font-cinzel text-xl tracking-wide text-stone-300">Зал гильдии просыпается...</p>
        </div>
      </main>
    );
  }

  if (isAuthenticated && loading) {
    return (
      <main className="guild-hub-bg flex min-h-screen items-center justify-center text-stone-100">
        <div className="text-center">
          <div className="mx-auto mb-4 h-16 w-16 rounded-full border-4 border-amber-400/70 border-t-transparent animate-spin" />
          <p className="font-cinzel text-xl tracking-wide text-stone-300">Зал гильдии просыпается...</p>
        </div>
      </main>
    );
  }

  if (isAuthenticated && profile) {
    return <AuthenticatedGuildHome profile={profile} />;
  }

  return <PublicGuildHub />;
}
