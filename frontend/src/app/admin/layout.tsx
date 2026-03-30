"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import AdminNav from "@/components/admin/AdminNav";
import {
  adminEnableTotp,
  adminGetPlatformStats,
  adminSetupTotp,
  getApiErrorMessage,
  getApiErrorStatus,
} from "@/lib/api";
import { isAdminTotpErrorMessage } from "@/lib/adminTotp";

function isValidTotpCode(value: string): boolean {
  return /^\d{6,8}$/.test(value.trim());
}

interface TotpSetupData {
  secret: string;
  otpauthUri: string;
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const {
    user,
    isAuthenticated,
    loading,
    adminTotpToken,
    adminTotpError,
    setAdminTotpToken,
    clearAdminTotpToken,
    clearAdminTotpError,
  } = useAuth();
  const router = useRouter();
  const [probeNonce, setProbeNonce] = useState(0);
  const [gateLoading, setGateLoading] = useState(true);
  const [requiresTotp, setRequiresTotp] = useState(false);
  const [gateError, setGateError] = useState<string | null>(null);
  const [totpInput, setTotpInput] = useState("");
  const [submitLoading, setSubmitLoading] = useState(false);
  const [setupLoading, setSetupLoading] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupToken, setSetupToken] = useState("");
  const [setupTokenLoading, setSetupTokenLoading] = useState(false);
  const [setupData, setSetupData] = useState<TotpSetupData | null>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace("/auth/login");
    }
  }, [loading, isAuthenticated, router]);

  useEffect(() => {
    if (loading || !isAuthenticated || user?.role !== "admin") {
      return;
    }

    let cancelled = false;

    const probeAdminAccess = async () => {
      setGateLoading(true);

      try {
        await adminGetPlatformStats();
        if (!cancelled) {
          setRequiresTotp(false);
          setGateError(null);
          clearAdminTotpError();
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        const status = getApiErrorStatus(error);
        const detail = getApiErrorMessage(
          error,
          "Не удалось проверить доступ к административным инструментам.",
        );

        if (status === 403 && isAdminTotpErrorMessage(detail)) {
          setRequiresTotp(true);
          setGateError(detail);
          return;
        }

        setRequiresTotp(false);
        setGateError(detail);
      } finally {
        if (!cancelled) {
          setGateLoading(false);
        }
      }
    };

    probeAdminAccess();

    return () => {
      cancelled = true;
    };
  }, [
    adminTotpToken,
    clearAdminTotpError,
    isAuthenticated,
    loading,
    probeNonce,
    user?.role,
  ]);

  const visibleGateError = useMemo(
    () => adminTotpError ?? gateError,
    [adminTotpError, gateError],
  );

  const isNotConfigured = visibleGateError?.toLowerCase().includes("not configured") ?? false;

  const refreshGate = () => {
    setProbeNonce((current) => current + 1);
  };

  const handleTotpSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!isValidTotpCode(totpInput)) {
      setGateError("Введите 6- или 8-значный код из приложения-аутентификатора.");
      return;
    }

    setSubmitLoading(true);
    setGateError(null);
    clearAdminTotpError();
    setAdminTotpToken(totpInput.trim());

    try {
      await adminGetPlatformStats();
      setTotpInput("");
      setRequiresTotp(false);
      refreshGate();
    } catch (error) {
      setGateError(getApiErrorMessage(error, "Не удалось подтвердить TOTP код."));
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleSetupStart = async () => {
    setSetupLoading(true);
    setSetupError(null);

    try {
      const response = await adminSetupTotp();
      setSetupData({
        secret: response.secret,
        otpauthUri: response.otpauth_uri,
      });
    } catch (error) {
      setSetupError(getApiErrorMessage(error, "Не удалось сгенерировать TOTP секрет."));
    } finally {
      setSetupLoading(false);
    }
  };

  const handleSetupConfirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!isValidTotpCode(setupToken)) {
      setSetupError("Введите 6- или 8-значный код для подтверждения настройки.");
      return;
    }

    setSetupTokenLoading(true);
    setSetupError(null);

    try {
      await adminEnableTotp(setupToken.trim());
      setSetupData(null);
      setSetupToken("");
      setGateError("TOTP настроен. Введите актуальный код, чтобы открыть admin-раздел.");
      refreshGate();
    } catch (error) {
      setSetupError(getApiErrorMessage(error, "Не удалось подтвердить TOTP настройку."));
    } finally {
      setSetupTokenLoading(false);
    }
  };

  if (loading || (isAuthenticated && user?.role === "admin" && gateLoading)) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-14 h-14 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500 font-mono text-sm uppercase tracking-wider">
            Проверка доступа...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-xl rounded-3xl border border-amber-500/25 bg-gray-900/90 p-8 shadow-2xl shadow-amber-950/20">
          <p className="text-xs font-mono uppercase tracking-[0.35em] text-amber-300/80">
            Access Denied
          </p>
          <h1 className="mt-4 text-3xl font-semibold text-white">
            Недостаточно прав для входа в админ-панель
          </h1>
          <p className="mt-4 text-sm leading-6 text-gray-300">
            Эта зона доступна только пользователям с ролью admin. Текущая сессия авторизована,
            но прав администратора у нее нет.
          </p>
          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={() => router.replace("/")}
              className="rounded-xl bg-amber-500 px-4 py-3 text-sm font-semibold text-black transition hover:bg-amber-400"
            >
              На главную
            </button>
            <button
              type="button"
              onClick={() => router.replace("/profile")}
              className="rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold text-gray-200 transition hover:border-white/30 hover:text-white"
            >
              В профиль
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (visibleGateError && !requiresTotp) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
        <div className="w-full max-w-xl rounded-3xl border border-red-500/30 bg-gray-900/90 p-8 shadow-2xl shadow-red-950/30">
          <p className="text-xs font-mono uppercase tracking-[0.35em] text-red-300/80">
            Admin Access Check Failed
          </p>
          <h1 className="mt-4 text-3xl font-semibold text-white">
            Админ-панель сейчас недоступна
          </h1>
          <p className="mt-4 text-sm leading-6 text-gray-300">
            {visibleGateError}
          </p>
          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={refreshGate}
              className="rounded-xl bg-red-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-400"
            >
              Повторить проверку
            </button>
            <button
              type="button"
              onClick={() => router.replace("/")}
              className="rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold text-gray-200 transition hover:border-white/30 hover:text-white"
            >
              На главную
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (requiresTotp) {
    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.18),_transparent_35%),linear-gradient(180deg,_#030712_0%,_#111827_100%)] px-4 py-10 text-white">
        <div className="mx-auto flex max-w-5xl flex-col gap-6 lg:flex-row">
          <section className="flex-1 rounded-3xl border border-amber-400/20 bg-black/40 p-8 shadow-2xl shadow-amber-950/20 backdrop-blur">
            <p className="text-xs font-mono uppercase tracking-[0.35em] text-amber-300/80">
              Admin TOTP Required
            </p>
            <h1 className="mt-4 text-3xl font-semibold text-white">
              Подтвердите текущий код доступа
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-gray-300">
              Административные маршруты уже защищены backend-контрактом `X-TOTP-Token`.
              Введите одноразовый код из приложения-аутентификатора, чтобы открыть панель
              и отправлять admin-запросы в рамках текущей сессии браузера.
            </p>

            {visibleGateError && (
              <div className="mt-6 rounded-2xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                {visibleGateError}
              </div>
            )}

            <form className="mt-8 space-y-4" onSubmit={handleTotpSubmit}>
              <label className="block text-xs font-mono uppercase tracking-[0.3em] text-gray-400">
                One-time code
              </label>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={8}
                value={totpInput}
                onChange={(event) => setTotpInput(event.target.value.replace(/\D/g, ""))}
                className="w-full rounded-2xl border border-white/10 bg-gray-950/80 px-4 py-4 text-lg tracking-[0.35em] text-white outline-none transition focus:border-amber-400/60"
                placeholder="123456"
                disabled={submitLoading}
              />
              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={submitLoading}
                  className="rounded-2xl bg-amber-400 px-5 py-3 text-sm font-semibold text-gray-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitLoading ? "Проверяем код..." : "Открыть admin-раздел"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setTotpInput("");
                    clearAdminTotpToken();
                    clearAdminTotpError();
                    refreshGate();
                  }}
                  className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-gray-200 transition hover:border-white/30 hover:text-white"
                >
                  Сбросить код
                </button>
              </div>
            </form>
          </section>

          <aside className="w-full max-w-xl rounded-3xl border border-white/10 bg-gray-900/80 p-8 shadow-2xl shadow-black/30">
            <p className="text-xs font-mono uppercase tracking-[0.35em] text-sky-300/80">
              Setup And Recovery
            </p>
            <h2 className="mt-4 text-2xl font-semibold text-white">
              {isNotConfigured ? "TOTP ещё не настроен" : "Нужен новый секрет или подтверждение?"}
            </h2>
            <p className="mt-4 text-sm leading-6 text-gray-300">
              Если backend сообщает, что Admin 2FA ещё не настроен, сгенерируйте секрет,
              добавьте его в приложение-аутентификатор и подтвердите настройку кодом.
            </p>

            {setupError && (
              <div className="mt-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                {setupError}
              </div>
            )}

            {!setupData && (
              <button
                type="button"
                onClick={handleSetupStart}
                disabled={setupLoading}
                className="mt-6 rounded-2xl bg-sky-400 px-5 py-3 text-sm font-semibold text-gray-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {setupLoading ? "Генерируем секрет..." : "Сгенерировать TOTP секрет"}
              </button>
            )}

            {setupData && (
              <div className="mt-6 space-y-5 rounded-2xl border border-sky-400/20 bg-sky-500/5 p-5">
                <div>
                  <p className="text-xs font-mono uppercase tracking-[0.25em] text-sky-200/70">
                    Secret
                  </p>
                  <p className="mt-2 break-all font-mono text-sm text-sky-50">
                    {setupData.secret}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-mono uppercase tracking-[0.25em] text-sky-200/70">
                    Otpauth URI
                  </p>
                  <p className="mt-2 break-all font-mono text-xs text-sky-100/90">
                    {setupData.otpauthUri}
                  </p>
                </div>
                <form className="space-y-4" onSubmit={handleSetupConfirm}>
                  <label className="block text-xs font-mono uppercase tracking-[0.25em] text-sky-200/70">
                    Verification code
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={8}
                    value={setupToken}
                    onChange={(event) => setSetupToken(event.target.value.replace(/\D/g, ""))}
                    className="w-full rounded-2xl border border-white/10 bg-gray-950/80 px-4 py-4 text-lg tracking-[0.35em] text-white outline-none transition focus:border-sky-400/60"
                    placeholder="123456"
                    disabled={setupTokenLoading}
                  />
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="submit"
                      disabled={setupTokenLoading}
                      className="rounded-2xl bg-sky-400 px-5 py-3 text-sm font-semibold text-gray-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {setupTokenLoading ? "Подтверждаем..." : "Подтвердить настройку"}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSetupData(null);
                        setSetupToken("");
                        setSetupError(null);
                      }}
                      className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-gray-200 transition hover:border-white/30 hover:text-white"
                    >
                      Отменить
                    </button>
                  </div>
                </form>
              </div>
            )}
          </aside>
        </div>
      </div>
    );
  }

  return (
    <div className="ops-grid-backdrop flex min-h-screen bg-[linear-gradient(180deg,#020617_0%,#09111d_100%)]">
      <AdminNav />
      <main className="flex-1 min-h-screen overflow-y-auto">
        <div className="max-w-7xl mx-auto p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}
