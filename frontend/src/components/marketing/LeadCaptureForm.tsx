"use client";

import { useState } from "react";
import { getApiErrorMessage, submitLeadCapture } from "@/lib/api";
import Button from "@/components/ui/Button";
import { getAttributionPayload } from "@/lib/attribution";

const budgetOptions = [
  "$300 - $1,500",
  "$700 - $2,500",
  "$800 - $3,000",
  "$1,200 - $4,000",
  "$4,000+",
];

interface LeadCaptureFormProps {
  source: string;
  title?: string;
  description?: string;
  useCasePreset?: string;
  compact?: boolean;
}

export default function LeadCaptureForm({
  source,
  title = "Оставьте вводный запрос",
  description = "Если задача ещё не готова к полноценной публикации, зафиксируйте контекст заранее и вернитесь к нему через клиентский маршрут.",
  useCasePreset,
  compact = false,
}: LeadCaptureFormProps) {
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [contactName, setContactName] = useState("");
  const [useCase, setUseCase] = useState(useCasePreset ?? "");
  const [budgetBand, setBudgetBand] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const attribution = getAttributionPayload();
      const response = await submitLeadCapture({
        email,
        company_name: companyName,
        contact_name: contactName,
        use_case: useCasePreset ?? useCase,
        budget_band: budgetBand || undefined,
        message: message || undefined,
        source,
        ...attribution,
      });
      setSuccess(`Запрос сохранён: ${response.email}`);
      setEmail("");
      setCompanyName("");
      setContactName("");
      setBudgetBand("");
      setMessage("");
      if (!useCasePreset) {
        setUseCase("");
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось сохранить запрос"));
    } finally {
      setLoading(false);
    }
  }

  const fieldClass = "w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm text-stone-100 outline-none transition-colors placeholder:text-stone-500 focus:border-amber-500/50";

  return (
    <form onSubmit={handleSubmit} className="rounded-[1.75rem] border border-white/10 bg-black/25 p-6 sm:p-7">
      <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Lead Capture</p>
      <h3 className="mt-3 font-cinzel text-2xl text-stone-100">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-stone-300">{description}</p>

      {success && <div className="mt-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{success}</div>}
      {error && <div className="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}

      <div className={`mt-6 grid gap-4 ${compact ? "lg:grid-cols-2" : "md:grid-cols-2"}`}>
        <input className={fieldClass} type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Work email" required />
        <input className={fieldClass} value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="Компания" required />
        <input className={fieldClass} value={contactName} onChange={(event) => setContactName(event.target.value)} placeholder="Контактное лицо" required />
        <select className={fieldClass} value={budgetBand} onChange={(event) => setBudgetBand(event.target.value)}>
          <option value="">Оценка бюджета</option>
          {budgetOptions.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </div>

      {!useCasePreset && (
        <input
          className={`${fieldClass} mt-4`}
          value={useCase}
          onChange={(event) => setUseCase(event.target.value)}
          placeholder="Какой сценарий хотите закрыть"
          required
        />
      )}

      {useCasePreset && (
        <div className="mt-4 inline-flex rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200">
          {useCasePreset}
        </div>
      )}

      <textarea
        className={`${fieldClass} mt-4 min-h-32`}
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Коротко опишите задачу, сроки и что сейчас блокирует запуск"
      />

      <Button type="submit" variant="primary" className="mt-5 px-8 py-4" loading={loading} loadingLabel="Сохраняем запрос">
        Сохранить вводный запрос
      </Button>
    </form>
  );
}