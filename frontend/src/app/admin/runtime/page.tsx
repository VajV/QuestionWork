"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  adminGetJobStatus,
  adminGetOperations,
  adminGetRuntimeHeartbeats,
  adminRequeueJob,
  getApiErrorMessage,
} from "@/lib/api";
import type {
  AdminJobStatusResponse,
  AdminOperationFeedEntry,
  AdminRuntimeHeartbeatEntry,
  AdminRuntimeHeartbeatsResponse,
} from "@/types";
import {
  Activity,
  AlertCircle,
  Clock3,
  Cpu,
  RefreshCw,
  RotateCcw,
  ServerCog,
  ShieldAlert,
} from "lucide-react";

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU");
}

function formatAgo(seconds: number): string {
  if (seconds < 60) return `${seconds}с`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}м`;
  return `${Math.floor(seconds / 3600)}ч`;
}

function statusTone(status: string | null | undefined): string {
  switch (status) {
    case "succeeded":
      return "text-emerald-300 border-emerald-500/30 bg-emerald-500/10";
    case "running":
      return "text-sky-300 border-sky-500/30 bg-sky-500/10";
    case "queued":
    case "retry_scheduled":
      return "text-amber-300 border-amber-500/30 bg-amber-500/10";
    case "failed":
    case "dead_letter":
      return "text-red-300 border-red-500/30 bg-red-500/10";
    default:
      return "text-slate-300 border-white/10 bg-white/5";
  }
}

export default function AdminRuntimePage() {
  const [heartbeats, setHeartbeats] = useState<AdminRuntimeHeartbeatsResponse | null>(null);
  const [operations, setOperations] = useState<AdminOperationFeedEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeOnly, setActiveOnly] = useState(true);

  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<AdminJobStatusResponse | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [requeueReason, setRequeueReason] = useState("");
  const [requeueLoading, setRequeueLoading] = useState(false);
  const [requeueMessage, setRequeueMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [heartbeatData, operationsData] = await Promise.all([
        adminGetRuntimeHeartbeats({ activeOnly, limit: 100 }),
        adminGetOperations(1, 25),
      ]);
      setHeartbeats(heartbeatData);
      setOperations(operationsData.items ?? []);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить runtime данные."));
    } finally {
      setLoading(false);
    }
  }, [activeOnly]);

  useEffect(() => {
    load();
  }, [load]);

  const lookupJob = useCallback(async (targetJobId: string) => {
    setJobLoading(true);
    setJobError(null);
    setRequeueMessage(null);
    try {
      const detail = await adminGetJobStatus(targetJobId);
      setJob(detail);
      setJobId(detail.id);
    } catch (err) {
      setJob(null);
      setJobError(getApiErrorMessage(err, "Не удалось загрузить job."));
    } finally {
      setJobLoading(false);
    }
  }, []);

  const handleLookupSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = jobId.trim();
    if (!trimmed) {
      setJobError("Введите ID job для просмотра деталей.");
      return;
    }
    await lookupJob(trimmed);
  };

  const handleRequeue = async () => {
    if (!job) return;
    setRequeueLoading(true);
    setRequeueMessage(null);
    try {
      const result = await adminRequeueJob(job.id, requeueReason);
      setRequeueMessage(result.message);
      await Promise.all([lookupJob(job.id), load()]);
    } catch (err) {
      setRequeueMessage(getApiErrorMessage(err, "Не удалось повторно поставить job в очередь."));
    } finally {
      setRequeueLoading(false);
    }
  };

  const runtimeRows: AdminRuntimeHeartbeatEntry[] = heartbeats?.runtimes ?? [];
  const canRequeue = job?.status === "dead_letter" || job?.status === "failed";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-cinzel font-bold text-white">Runtime Ops</h1>
          <p className="mt-1 text-sm text-slate-400">
            Heartbeats worker/scheduler, последние trust-layer операции и ручной replay проблемных jobs.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(event) => setActiveOnly(event.target.checked)}
              className="accent-sky-400"
            />
            Только активные runtimes
          </label>
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-2 rounded-xl border border-sky-500/25 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-100 transition hover:border-sky-400/40 hover:bg-sky-500/15"
          >
            <RefreshCw size={16} />
            Обновить
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200 flex items-start gap-3">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-400">Активные worker</span>
            <Cpu size={18} className="text-sky-300" />
          </div>
          <div className="mt-3 text-3xl font-semibold text-white">{heartbeats?.active_workers ?? 0}</div>
          <div className="mt-2 text-xs text-slate-500">stale: {heartbeats?.stale_workers ?? 0}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-400">Активные scheduler</span>
            <ServerCog size={18} className="text-violet-300" />
          </div>
          <div className="mt-3 text-3xl font-semibold text-white">{heartbeats?.active_schedulers ?? 0}</div>
          <div className="mt-2 text-xs text-slate-500">leader: {heartbeats?.leader_runtime_id ?? "-"}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-400">Всего отображено</span>
            <Activity size={18} className="text-emerald-300" />
          </div>
          <div className="mt-3 text-3xl font-semibold text-white">{heartbeats?.total ?? 0}</div>
          <div className="mt-2 text-xs text-slate-500">generated: {heartbeats ? formatDateTime(heartbeats.generated_at) : "-"}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-400">Stale runtimes</span>
            <ShieldAlert size={18} className="text-amber-300" />
          </div>
          <div className="mt-3 text-3xl font-semibold text-white">{heartbeats?.stale_total ?? 0}</div>
          <div className="mt-2 text-xs text-slate-500">leader count: {heartbeats?.leader_count ?? 0}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <section className="rounded-3xl border border-white/10 bg-slate-950/80 p-5 shadow-[0_0_40px_rgba(2,6,23,0.25)]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Runtime heartbeats</h2>
              <p className="mt-1 text-sm text-slate-500">Состояние worker/scheduler по heartbeat и lease metadata.</p>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-slate-500">
                <tr className="border-b border-white/10">
                  <th className="pb-3 pr-4 font-medium">Kind</th>
                  <th className="pb-3 pr-4 font-medium">Runtime</th>
                  <th className="pb-3 pr-4 font-medium">Queue/leader</th>
                  <th className="pb-3 pr-4 font-medium">Last seen</th>
                  <th className="pb-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-500">Загрузка runtime heartbeats...</td>
                  </tr>
                ) : runtimeRows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-500">Нет runtime heartbeats для выбранного фильтра.</td>
                  </tr>
                ) : (
                  runtimeRows.map((runtime) => (
                    <tr key={runtime.id} className="border-b border-white/5 align-top">
                      <td className="py-3 pr-4">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${runtime.is_stale ? "text-red-300 border-red-500/30 bg-red-500/10" : "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"}`}>
                          {runtime.runtime_kind}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-slate-200">
                        <div className="font-mono text-xs">{runtime.runtime_id}</div>
                        <div className="mt-1 text-xs text-slate-500">{runtime.hostname}:{runtime.pid}</div>
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        <div>{runtime.queue_name ?? (runtime.is_leader ? "leader" : "-")}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          {runtime.is_leader ? `lease ttl ${runtime.lease_ttl_seconds ?? 0}s` : `heartbeat ${runtime.heartbeat_interval_seconds}s`}
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        <div>{formatAgo(runtime.seconds_since_last_seen)}</div>
                        <div className="mt-1 text-xs text-slate-500">{formatDateTime(runtime.last_seen_at)}</div>
                      </td>
                      <td className="py-3 text-slate-300">
                        <div>{formatAgo(runtime.started_age_seconds)}</div>
                        <div className="mt-1 text-xs text-slate-500">{formatDateTime(runtime.started_at)}</div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-3xl border border-white/10 bg-slate-950/80 p-5 shadow-[0_0_40px_rgba(2,6,23,0.25)]">
          <h2 className="text-lg font-semibold text-white">Job lookup & replay</h2>
          <p className="mt-1 text-sm text-slate-500">Открой конкретный trust-layer job и при необходимости вручную верни его в очередь.</p>

          <form onSubmit={handleLookupSubmit} className="mt-4 flex gap-3">
            <input
              value={jobId}
              onChange={(event) => setJobId(event.target.value)}
              placeholder="job UUID"
              className="flex-1 rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none transition focus:border-sky-400/40"
            />
            <button
              type="submit"
              disabled={jobLoading}
              className="rounded-xl border border-sky-500/25 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-100 transition hover:border-sky-400/40 hover:bg-sky-500/15 disabled:opacity-60"
            >
              {jobLoading ? "Поиск..." : "Найти"}
            </button>
          </form>

          {jobError ? <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{jobError}</div> : null}

          {job ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-slate-400">{job.id}</span>
                  <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(job.status)}`}>
                    {job.status}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 text-sm text-slate-300 sm:grid-cols-2">
                  <div>Kind: <span className="text-white">{job.kind}</span></div>
                  <div>Queue: <span className="text-white">{job.queue_name}</span></div>
                  <div>Attempts: <span className="text-white">{job.attempt_count}/{job.max_attempts}</span></div>
                  <div>Publish attempts: <span className="text-white">{job.queue_publish_attempts}</span></div>
                  <div>Last enqueue: <span className="text-white">{formatDateTime(job.enqueued_at)}</span></div>
                  <div>Available at: <span className="text-white">{formatDateTime(job.available_at)}</span></div>
                </div>
                {(job.last_error || job.last_enqueue_error) ? (
                  <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
                    <div>Last error: {job.last_error ?? "-"}</div>
                    <div className="mt-1">Enqueue error: {job.last_enqueue_error ?? "-"}</div>
                  </div>
                ) : null}
              </div>

              {job.command ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 text-sm text-slate-300">
                  <div className="font-medium text-white">Linked command</div>
                  <div className="mt-2">{job.command.command_kind}</div>
                  <div className="mt-1 text-slate-500">{job.command.id} • status {job.command.status}</div>
                </div>
              ) : null}

              <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                <label className="block text-sm text-slate-400">Причина ручного replay</label>
                <textarea
                  value={requeueReason}
                  onChange={(event) => setRequeueReason(event.target.value)}
                  placeholder="Что было исправлено или почему job можно безопасно повторить"
                  className="mt-2 h-24 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-sky-400/40"
                />
                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleRequeue}
                    disabled={!canRequeue || requeueLoading}
                    className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:border-emerald-400/40 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RotateCcw size={16} />
                    {requeueLoading ? "Повторная постановка..." : "Повторно поставить в очередь"}
                  </button>
                  {!canRequeue ? <span className="text-xs text-slate-500">Replay доступен только для `failed` и `dead_letter` jobs.</span> : null}
                </div>
                {requeueMessage ? (
                  <div className={`mt-3 rounded-xl border px-3 py-2 text-sm ${requeueMessage.toLowerCase().includes("не удалось") ? "border-red-500/30 bg-red-500/10 text-red-200" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"}`}>
                    {requeueMessage}
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                <div className="text-sm font-medium text-white">Attempt history</div>
                <div className="mt-3 space-y-2">
                  {job.attempts.length === 0 ? (
                    <div className="text-sm text-slate-500">Попыток выполнения пока нет.</div>
                  ) : (
                    job.attempts.map((attempt) => (
                      <div key={attempt.id} className="rounded-xl border border-white/5 bg-slate-950/70 px-3 py-2 text-sm text-slate-300">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-white">Attempt #{attempt.attempt_no}</span>
                          <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] ${statusTone(attempt.status)}`}>{attempt.status}</span>
                          <span className="text-slate-500">{attempt.worker_id}</span>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          start {formatDateTime(attempt.started_at)}
                          {attempt.finished_at ? ` • finish ${formatDateTime(attempt.finished_at)}` : ""}
                          {attempt.duration_ms !== null ? ` • ${attempt.duration_ms} ms` : ""}
                        </div>
                        {attempt.error_text ? <div className="mt-1 text-xs text-amber-200">{attempt.error_text}</div> : null}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </section>
      </div>

      <section className="rounded-3xl border border-white/10 bg-slate-950/80 p-5 shadow-[0_0_40px_rgba(2,6,23,0.25)]">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Recent trust-layer operations</h2>
            <p className="mt-1 text-sm text-slate-500">Последние admin-triggered команды и их job статусы.</p>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr className="border-b border-white/10">
                <th className="pb-3 pr-4 font-medium">Action</th>
                <th className="pb-3 pr-4 font-medium">Command</th>
                <th className="pb-3 pr-4 font-medium">Job</th>
                <th className="pb-3 pr-4 font-medium">Actor</th>
                <th className="pb-3 font-medium">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {operations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">Нет runtime операций для отображения.</td>
                </tr>
              ) : (
                operations.map((item) => (
                  <tr key={`${item.command_id}:${item.job_id ?? "none"}`} className="border-b border-white/5 align-top">
                    <td className="py-3 pr-4 text-slate-200">
                      <div>{item.action}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.queue_name ?? "-"}</div>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(item.command_status)}`}>
                        {item.command_status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-slate-300">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(item.job_status)}`}>
                          {item.job_status ?? "-"}
                        </span>
                        {item.job_id ? (
                          <button
                            type="button"
                            onClick={() => lookupJob(item.job_id!)}
                            className="font-mono text-xs text-sky-300 transition hover:text-sky-100"
                          >
                            {item.job_id}
                          </button>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-slate-300">{item.actor_admin_id ?? item.actor_user_id ?? "-"}</td>
                    <td className="py-3 text-slate-300">
                      <div className="inline-flex items-center gap-2"><Clock3 size={14} className="text-slate-500" />{formatDateTime(item.submitted_at)}</div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}