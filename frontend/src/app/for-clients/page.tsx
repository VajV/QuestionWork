import Header from "@/components/layout/Header";
import ClientProofStrip from "@/components/marketing/ClientProofStrip";
import ClientTrustGrid from "@/components/marketing/ClientTrustGrid";
import LeadCaptureForm from "@/components/marketing/LeadCaptureForm";
import LiveTrustProof from "@/components/marketing/LiveTrustProof";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

const useCaseLinks = [
  {
    href: "/hire/fastapi-backend",
    title: "FastAPI Backend",
    text: "API, async workflows, auth, integrations и production hardening.",
  },
  {
    href: "/hire/nextjs-dashboard",
    title: "Next.js Dashboard",
    text: "Кабинеты, внутренние панели и data-heavy workflows для команды и клиентов.",
  },
  {
    href: "/hire/urgent-bugfix",
    title: "Urgent Bugfix",
    text: "Инциденты, критичные баги, release recovery и быстрый production repair.",
  },
  {
    href: "/hire/mvp-sprint",
    title: "MVP Sprint",
    text: "Короткий delivery-блок под новый продуктовый поток или запуск функции.",
  },
];

const hiringSteps = [
  {
    step: "01",
    title: "Опишите задачу как рабочий контракт",
    text: "Сначала клиент фиксирует стек, рамки, сроки и ожидаемый результат. Это снимает часть хаоса ещё до откликов.",
  },
  {
    step: "02",
    title: "Сравните исполнителей по полезным сигналам",
    text: "Дальше важны стек, качество профиля, релевантность опыта и готовность к нужному типу delivery, а не только цена и скорость ответа.",
  },
  {
    step: "03",
    title: "Доведите работу до подтверждённой сдачи",
    text: "Сделка должна завершаться предсказуемо: с понятным статусом, безопасным потоком оплаты и ясным сценарием на случай спорных ситуаций.",
  },
];

const painPoints = [
  "Нужно срочно закрыть backend или integration block, а не искать неделями по шумному маркетплейсу.",
  "Нужна внятная рамка сделки: кто делает, в каком стеке, когда сдаёт и что происходит при споре.",
  "Нужен маршрут для первого найма, если заказчик ещё не привык формулировать задачу как контракт.",
];

export default function ForClientsPage() {
  return (
    <main id="main-content" className="guild-hub-bg min-h-screen text-stone-100">
      <Header />

      <section className="relative overflow-hidden border-b border-white/6">
        <div className="container mx-auto px-4 py-12 sm:py-16 lg:py-20">
          <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-start">
            <div>
              <div className="guild-chip inline-flex">Для клиентов и hiring leads</div>
              <h1 className="mt-5 max-w-4xl font-cinzel text-5xl font-bold leading-[0.95] text-stone-100 sm:text-6xl">
                Нанимайте IT-специалистов через
                <span className="block bg-gradient-to-r from-amber-300 via-stone-100 to-sky-300 bg-clip-text text-transparent">
                  понятный контрактный маршрут
                </span>
              </h1>
              <p className="mt-6 max-w-3xl text-base leading-8 text-stone-300 sm:text-lg">
                QuestionWork строит клиентский путь вокруг доверия и операционной ясности: кого можно нанять,
                как проходит сделка, где клиент видит риски заранее и какой следующий шаг нужен прямо сейчас.
              </p>

              <div className="mt-8 flex flex-col gap-4 sm:flex-row">
                <Button href="/quests/create" variant="primary" className="px-8 py-4 text-sm sm:text-base">
                  Опубликовать квест
                </Button>
                <Button href="/marketplace" variant="secondary" className="border-stone-600/60 bg-black/25 px-8 py-4 text-sm sm:text-base">
                  Смотреть специалистов
                </Button>
              </div>

              <div className="mt-8 space-y-3">
                {painPoints.map((point) => (
                  <div key={point} className="rounded-2xl border border-white/10 bg-black/25 px-5 py-4 text-sm leading-7 text-stone-300">
                    {point}
                  </div>
                ))}
              </div>
            </div>

            <Card className="border-white/10 bg-gradient-to-br from-slate-950/90 via-stone-950/90 to-black p-8">
              <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Почему это не generic freelance chaos</p>
              <h2 className="mt-4 font-cinzel text-3xl text-stone-100">Клиент видит процесс до регистрации</h2>
              <p className="mt-4 text-sm leading-7 text-stone-300">
                Здесь клиентский маршрут не прячется за RPG-оболочкой. Платформа должна заранее объяснять стек задач,
                защиту сделки, ход найма и точки принятия решения.
              </p>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Process</p>
                  <p className="mt-3 text-sm leading-7 text-stone-300">Бриф, отбор, исполнение и сдача собраны в один путь вместо набора несвязанных экранов.</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Protection</p>
                  <p className="mt-3 text-sm leading-7 text-stone-300">Escrow и dispute summary выведены в клиентскую зону как явные trust-блоки, а не скрыты в документации.</p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <div className="max-w-3xl">
          <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Как проходит найм</p>
          <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Путь клиента должен быть читаемым, а не магическим</h2>
          <p className="mt-4 text-sm leading-7 text-stone-400 sm:text-base">
            Новому заказчику важно понять, как он переходит от задачи к исполнителю и что платформа делает для снижения риска на каждом шаге.
          </p>
        </div>

        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {hiringSteps.map((item) => (
            <Card key={item.step} className="h-full border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-7">
              <p className="font-mono text-xs uppercase tracking-[0.3em] text-sky-300/80">Шаг {item.step}</p>
              <h3 className="mt-4 font-cinzel text-2xl text-stone-100">{item.title}</h3>
              <p className="mt-4 text-sm leading-7 text-stone-300">{item.text}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-y border-white/6 bg-black/18">
        <div className="container mx-auto px-4 py-20">
          <div className="max-w-3xl">
            <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Proof Layer</p>
            <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Доверие должно быть явным, а не подразумеваемым</h2>
            <p className="mt-4 text-sm leading-7 text-stone-400 sm:text-base">
              Этот слой нужен не для украшения лендинга, а чтобы клиент до старта понял механику сделки, ограничения и основания для выбора исполнителя.
            </p>
          </div>

            <LiveTrustProof className="mt-10" />
          <ClientProofStrip className="mt-10" />
          <ClientTrustGrid className="mt-10" />
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <div className="max-w-3xl">
          <p className="font-mono text-xs uppercase tracking-[0.32em] text-amber-400/80">Use Cases</p>
          <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">Выберите hiring-вход под ваш сценарий</h2>
          <p className="mt-4 text-sm leading-7 text-stone-400 sm:text-base">
            Вместо одной общей страницы клиент может зайти через конкретный use case и быстрее понять бюджет, рамки и следующий шаг.
          </p>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {useCaseLinks.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-2xl border border-white/10 bg-black/25 px-5 py-5 transition-colors hover:border-amber-500/40"
            >
              <h3 className="font-cinzel text-2xl text-stone-100">{item.title}</h3>
              <p className="mt-3 text-sm leading-7 text-stone-300">{item.text}</p>
            </a>
          ))}
        </div>
      </section>

      <section className="container mx-auto px-4 py-20">
        <LeadCaptureForm source="for_clients_page" />
      </section>
    </main>
  );
}