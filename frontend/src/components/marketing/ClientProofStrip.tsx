import Card from "@/components/ui/Card";

const proofItems = [
  {
    label: "Что закрывают здесь",
    title: "Backend, dashboards, integrations",
    text: "Платформа ориентирована на IT-работы с понятным результатом: API, dashboards, audits, urgent fixes и delivery-потоки.",
    accent: "text-amber-300",
  },
  {
    label: "Как клиент двигается",
    title: "Бриф -> отбор -> сдача",
    text: "Заказчик не начинает с хаоса. Сначала рамка задачи, затем исполнители и только потом подтверждённое исполнение.",
    accent: "text-sky-300",
  },
  {
    label: "Почему спокойнее",
    title: "Escrow и спорные сценарии",
    text: "Путь сделки опирается на контролируемый контрактный поток, а не на разрозненные договорённости в личке.",
    accent: "text-emerald-300",
  },
  {
    label: "Что видно заранее",
    title: "Стек, рамки, следующий шаг",
    text: "Клиент с первой страницы понимает, кого можно нанять, на что смотреть при выборе и куда идти дальше.",
    accent: "text-violet-300",
  },
];

interface ClientProofStripProps {
  className?: string;
}

export default function ClientProofStrip({ className = "" }: ClientProofStripProps) {
  return (
    <section className={className}>
      <div className="grid gap-4 lg:grid-cols-4">
        {proofItems.map((item) => (
          <Card
            key={item.title}
            className="h-full border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-5"
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">{item.label}</p>
            <h3 className={`mt-3 font-cinzel text-2xl ${item.accent}`}>{item.title}</h3>
            <p className="mt-3 text-sm leading-7 text-stone-300">{item.text}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}