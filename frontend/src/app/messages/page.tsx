"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import { useAuth } from "@/context/AuthContext";
import { getApiErrorMessage, getQuestDialogs, type QuestDialog } from "@/lib/api";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MessagesPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [dialogs, setDialogs] = useState<QuestDialog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    async function loadDialogs() {
      setLoading(true);
      setError(null);
      try {
        const data = await getQuestDialogs(100, 0);
        setDialogs(data.dialogs);
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, "Не удалось загрузить диалоги"));
      } finally {
        setLoading(false);
      }
    }

    if (!authLoading && isAuthenticated) {
      loadDialogs();
    }
  }, [authLoading, isAuthenticated]);

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gray-950 text-gray-200">
        <Header />
        <div className="container mx-auto max-w-5xl px-4 py-8">
          <Card className="p-10 text-center">Загрузка диалогов...</Card>
        </div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const unreadDialogs = dialogs.filter((dialog) => dialog.unread_count > 0).length;

  return (
    <main className="guild-world-shell min-h-screen bg-[linear-gradient(180deg,#090c12_0%,#101521_100%)] text-gray-200">
      <Header />
      <div className="container mx-auto max-w-5xl px-4 py-8">
        <GuildStatusStrip
          mode="guild"
          eyebrow="Communication hub"
          title="Диалоги по контрактам встроены в общий guild-layer"
          description="Контрактные переговоры, системные реплики и непрочитанные сигналы теперь читаются как часть общего мира гильдии, а не как отдельный технический список."
          stats={[
            { label: "Диалоги", value: dialogs.length, note: "активные ветки", tone: "cyan" },
            { label: "Unread", value: unreadDialogs, note: "требуют ответа", tone: unreadDialogs > 0 ? "amber" : "slate" },
            { label: "Silent", value: dialogs.filter((dialog) => !dialog.last_message_text).length, note: "без последней реплики", tone: "slate" },
            { label: "System", value: dialogs.filter((dialog) => dialog.last_message_type === "system").length, note: "системные заметки", tone: "purple" },
          ]}
          signals={[
            { label: unreadDialogs > 0 ? "response pressure active" : "response flow stable", tone: unreadDialogs > 0 ? "amber" : "emerald" },
            { label: dialogs.length > 0 ? "contract talks online" : "channel archive quiet", tone: dialogs.length > 0 ? "cyan" : "slate" },
          ]}
          className="mb-6"
        />

        <SeasonFactionRail mode="messages" unreadCount={unreadDialogs} className="mb-6" />

        <WorldPanel
          eyebrow="Conversation ledger"
          title="Каждый диалог привязан к реальному контракту и его статусу"
          description="Такой каркас унифицирует сообщения с остальными внутренними страницами: сверху world-state, ниже содержимое конкретного потока."
          tone="cyan"
          className="mb-8"
          compact
        />

        {error ? (
          <WorldPanel eyebrow="Channel fault" title="Не удалось открыть коммуникационный узел" tone="slate">
            <p className="text-center text-red-400">{error}</p>
          </WorldPanel>
        ) : dialogs.length === 0 ? (
          <WorldPanel eyebrow="Silent board" title="Пока нет активных диалогов" tone="slate">
            <p className="text-center text-gray-400">Сообщения появятся, когда по контрактам начнётся движение.</p>
          </WorldPanel>
        ) : (
          <div className="space-y-4">
            {dialogs.map((dialog) => (
              <Link
                key={dialog.quest_id}
                href={`/quests/${dialog.quest_id}`}
                className="block"
              >
                <Card className="border border-gray-800 bg-black/30 p-5 transition-colors hover:border-purple-700/40 hover:bg-purple-950/10">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-3">
                        <h2 className="truncate text-lg font-cinzel font-bold text-white">{dialog.quest_title}</h2>
                        <QuestStatusBadge status={dialog.quest_status} />
                        {dialog.unread_count > 0 && (
                          <span className="rounded-full bg-amber-500/20 px-2.5 py-1 text-xs font-mono text-amber-300">
                            {dialog.unread_count} unread
                          </span>
                        )}
                      </div>
                      <div className="mb-3 text-sm text-gray-500">
                        Собеседник: <span className="text-amber-400">{dialog.other_username || "участник контракта"}</span>
                      </div>
                      <div className="rounded-xl border border-gray-800 bg-gray-950/60 px-4 py-3 text-sm text-gray-300">
                        {dialog.last_message_text ? (
                          <>
                            {dialog.last_message_type === "system" && <span className="mr-2 text-amber-400">✨</span>}
                            {dialog.last_message_text}
                          </>
                        ) : (
                          <span className="text-gray-500">Сообщений пока нет.</span>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 text-xs font-mono uppercase tracking-wider text-gray-500">
                      {formatDate(dialog.last_message_at)}
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
