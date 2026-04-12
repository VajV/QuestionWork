"use client";

import { useEffect, useState } from "react";
import {
  getMyReferralInfo,
  generateReferralCode,
  ReferralInfo,
  isApiError,
} from "@/lib/api";

interface Props {
  className?: string;
}

export function ReferralPanel({ className = "" }: Props) {
  const [info, setInfo] = useState<ReferralInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let mounted = true;
    getMyReferralInfo()
      .then((data) => { if (mounted) setInfo(data); })
      .catch((err) => { if (mounted) setError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка"); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateReferralCode();
      setInfo(result);
    } catch (err) {
      setError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка генерации");
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!info?.code) return;
    try {
      await navigator.clipboard.writeText(info.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard may fail in non-secure contexts */ }
  };

  return (
    <div className={`rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-4 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">🎁</span>
        <span className="font-semibold text-white">Реферальная программа</span>
      </div>

      {loading && <div className="h-12 rounded bg-white/5 animate-pulse" />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && !error && info && (
        <div className="space-y-3">
          {info.code ? (
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-black/30 rounded px-3 py-1.5 text-sm text-indigo-300 font-mono tracking-widest border border-white/10">
                {info.code}
              </code>
              <button
                onClick={handleCopy}
                className="text-xs px-3 py-1.5 rounded bg-indigo-600/50 hover:bg-indigo-600 text-white transition-colors"
              >
                {copied ? "✓" : "Копировать"}
              </button>
            </div>
          ) : (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="w-full py-2 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              {generating ? "Генерация..." : "Получить реферальный код"}
            </button>
          )}

          <div className="flex gap-4 text-xs text-white/40">
            <span>Приглашено: <span className="text-white/70">{info.total_referred}</span></span>
            <span>Награждено: <span className="text-green-400">{info.rewarded_count}</span></span>
          </div>
          <p className="text-xs text-white/30">
            Пригласите друга по вашему коду. Когда он завершит первый квест, вы оба получите бонус XP.
          </p>
        </div>
      )}

      {!loading && !error && !info && (
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="w-full py-2 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {generating ? "Генерация..." : "Получить реферальный код"}
        </button>
      )}
    </div>
  );
}
