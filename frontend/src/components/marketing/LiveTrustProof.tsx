"use client";

import Card from "@/components/ui/Card";
import { useWorldMeta } from "@/context/WorldMetaContext";

interface LiveTrustProofProps {
  className?: string;
}

export default function LiveTrustProof({ className = "" }: LiveTrustProofProps) {
  const { snapshot, loading } = useWorldMeta();

  const proofCards = snapshot
    ? [
        {
          label: "Подтверждённые сдачи за 7 дней",
          value: String(snapshot.metrics.confirmed_quests_week),
          note: "Живой показатель по подтверждённым контрактам, а не маркетинговая цифра из лендинга.",
        },
        {
          label: "Открытые задачи сейчас",
          value: String(snapshot.metrics.open_quests),
          note: "Показывает текущий видимый спрос на платформе и помогает понять активность рынка.",
        },
        {
          label: snapshot.metrics.avg_rating !== null ? "Отзывы и средний рейтинг" : "Отзывы по завершённым задачам",
          value:
            snapshot.metrics.avg_rating !== null
              ? `${snapshot.metrics.avg_rating.toFixed(1)} / ${snapshot.metrics.total_reviews}`
              : String(snapshot.metrics.total_reviews),
          note:
            snapshot.metrics.avg_rating !== null
              ? "Слева средняя оценка, справа число отзывов. Оба значения приходят из live meta endpoint."
              : "Показываем только реальные отзывы, если средняя оценка ещё не сформировалась.",
        },
      ]
    : [
        {
          label: "Live signals",
          value: loading ? "Syncing" : "Unavailable",
          note: "Здесь показываются только live metrics из платформы. Если API недоступен, декоративные fake counts не подставляются.",
        },
      ];

  const generatedAt = snapshot
    ? new Date(snapshot.generated_at).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <section className={className}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Live Trust Proof</p>
          <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Показываем только то, что можно посчитать честно</h2>
          <p className="mt-4 text-sm leading-7 text-stone-400 sm:text-base">
            Вместо вымышленных побед и случайных чисел страницы для спроса опираются на live marketplace metrics и на явное объяснение process safety.
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/25 px-5 py-4 text-sm text-stone-300">
          {generatedAt ? `Обновлено: ${generatedAt}` : loading ? "Live данные синхронизируются" : "Live данные сейчас недоступны"}
        </div>
      </div>

      <div className={`mt-10 grid gap-4 ${proofCards.length > 1 ? "md:grid-cols-3" : "md:grid-cols-1"}`}>
        {proofCards.map((item) => (
          <Card key={item.label} className="h-full border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">{item.label}</p>
            <div className="mt-4 font-cinzel text-4xl text-amber-300">{item.value}</div>
            <p className="mt-4 text-sm leading-7 text-stone-300">{item.note}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}