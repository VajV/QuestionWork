import Link from "next/link";
import Header from "@/components/layout/Header";
import ClientProofStrip from "@/components/marketing/ClientProofStrip";
import LeadCaptureForm from "@/components/marketing/LeadCaptureForm";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

interface RelatedPageLink {
  href: string;
  label: string;
}

interface HireUseCaseTemplateProps {
  eyebrow: string;
  title: string;
  description: string;
  budgetBand: string;
  recommendedQuestTemplate: string;
  outcomes: string[];
  relatedPages: RelatedPageLink[];
  leadCaptureSource: string;
}

export default function HireUseCaseTemplate({
  eyebrow,
  title,
  description,
  budgetBand,
  recommendedQuestTemplate,
  outcomes,
  relatedPages,
  leadCaptureSource,
}: HireUseCaseTemplateProps) {
  return (
    <main id="main-content" className="guild-hub-bg min-h-screen text-stone-100">
      <Header />

      <section className="border-b border-white/6">
        <div className="container mx-auto px-4 py-12 sm:py-16 lg:py-20">
          <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-start">
            <div>
              <div className="guild-chip inline-flex">{eyebrow}</div>
              <h1 className="mt-5 max-w-4xl font-cinzel text-5xl font-bold leading-[0.95] text-stone-100 sm:text-6xl">
                {title}
              </h1>
              <p className="mt-6 max-w-3xl text-base leading-8 text-stone-300 sm:text-lg">
                {description}
              </p>

              <div className="mt-8 flex flex-col gap-4 sm:flex-row">
                <Button href="/quests/create" variant="primary" className="px-8 py-4 text-sm sm:text-base">
                  Опубликовать квест
                </Button>
                <Button href="/marketplace" variant="secondary" className="border-stone-600/60 bg-black/25 px-8 py-4 text-sm sm:text-base">
                  Смотреть специалистов
                </Button>
              </div>
            </div>

            <Card className="border-white/10 bg-gradient-to-br from-slate-950/90 via-stone-950/90 to-black p-8">
              <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Ориентир по сделке</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Budget Band</p>
                  <p className="mt-3 font-cinzel text-3xl text-amber-300">{budgetBand}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Quest Template</p>
                  <p className="mt-3 text-sm leading-7 text-stone-300">{recommendedQuestTemplate}</p>
                </div>
              </div>

              <div className="mt-6 rounded-2xl border border-white/10 bg-black/25 p-5">
                <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Если не готовы публиковать сразу</p>
                <p className="mt-3 text-sm leading-7 text-stone-300">
                  Сначала пройдите клиентский хаб, чтобы собрать рамку задачи и понять контрактный поток до регистрации.
                </p>
                <Button href="/for-clients" variant="ghost" className="mt-4 justify-start px-0 py-0 text-amber-300 hover:text-amber-200">
                  Открыть маршрут для заказчиков
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <div className="max-w-3xl">
          <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Типичный результат</p>
          <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Что клиент обычно хочет получить на выходе</h2>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {outcomes.map((outcome) => (
            <Card key={outcome} className="h-full border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-6">
              <p className="text-sm leading-7 text-stone-300">{outcome}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-y border-white/6 bg-black/18">
        <div className="container mx-auto px-4 py-20">
          <div className="max-w-3xl">
            <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Trust Layer</p>
            <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Клиент должен понимать не только стек, но и механику сделки</h2>
          </div>
          <ClientProofStrip className="mt-10" />
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <LeadCaptureForm
          source={leadCaptureSource}
          title="Не готовы публиковать квест прямо сейчас?"
          description="Оставьте вводный запрос по этому use case и вернитесь к нему, когда будете готовы двигаться в full quest posting flow."
          useCasePreset={title}
          compact
        />
      </section>

      <section className="container mx-auto px-4 py-20">
        <div className="max-w-3xl">
          <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Смежные сценарии</p>
          <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Посмотрите соседние hiring-входы</h2>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {relatedPages.map((page) => (
            <Link
              key={page.href}
              href={page.href}
              className="rounded-2xl border border-white/10 bg-black/25 px-5 py-4 text-sm font-medium text-stone-300 transition-colors hover:border-amber-500/40 hover:text-amber-200"
            >
              {page.label}
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}