import Card from "@/components/ui/Card";

const trustBlocks = [
  {
    title: "Бриф без догадок",
    text: "Клиенту проще сформулировать задачу через стек, сроки, бюджет и формат сдачи, а не через абстрактное описание в свободной форме.",
  },
  {
    title: "Ожидаемый процесс сделки",
    text: "Маршрут найма объясняет, что происходит до старта, во время исполнения и в момент подтверждения результата.",
  },
  {
    title: "Escrow как базовая защита",
    text: "Безопасность сделки должна быть частью интерфейса, а не скрытой деталью, которую клиент узнаёт постфактум.",
  },
  {
    title: "Dispute path без сюрпризов",
    text: "Если ожидания расходятся, у клиента должен быть понятный сценарий действий, а не ощущение, что спор решается вручную где-то за сценой.",
  },
  {
    title: "Профили с полезными сигналами",
    text: "При выборе исполнителя важны стек, релевантный опыт, качество профиля и признаки операционной надёжности, а не только RPG-атмосфера.",
  },
  {
    title: "Следующий CTA виден заранее",
    text: "Клиенту не нужно угадывать, что делать дальше: посмотреть специалистов, подготовить квест или пройти клиентский маршрут.",
  },
];

interface ClientTrustGridProps {
  className?: string;
}

export default function ClientTrustGrid({ className = "" }: ClientTrustGridProps) {
  return (
    <section className={className}>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {trustBlocks.map((block) => (
          <Card
            key={block.title}
            className="h-full border-white/10 bg-gradient-to-br from-slate-950/90 via-stone-950/90 to-black p-6"
          >
            <h3 className="font-cinzel text-2xl text-stone-100">{block.title}</h3>
            <p className="mt-4 text-sm leading-7 text-stone-300">{block.text}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}