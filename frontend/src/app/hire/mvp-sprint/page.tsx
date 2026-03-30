import type { Metadata } from "next";
import HireUseCaseTemplate from "@/components/marketing/HireUseCaseTemplate";

export const metadata: Metadata = {
  title: "Hire MVP Sprint Teams | QuestionWork",
  description: "Соберите MVP sprint под новый продуктовый поток, клиентский кабинет или внутренний инструмент через QuestionWork hiring surfaces.",
};

export default function HireMvpSprintPage() {
  return (
    <HireUseCaseTemplate
      eyebrow="Hire Use Case • MVP Sprint"
      title="Найм под короткий MVP sprint и быстрый продуктовый запуск"
      description="Этот сценарий нужен, когда клиенту не требуется огромная команда на полгода, а нужен сфокусированный delivery-блок под новый поток, кабинет или продуктовую гипотезу."
      budgetBand="$1,200 - $4,000"
      recommendedQuestTemplate="MVP sprint / launch block"
      outcomes={[
        "Собранный короткий delivery-спринт под конкретный продуктовый outcome, а не абстрактная разработка без рамок.",
        "Быстрый запуск функции, кабинета или внутреннего инструмента с понятной зоной ответственности.",
        "Синхронизация backend, frontend и release scope вокруг одного бизнес-результата.",
        "Основа для следующего квартала без необходимости сразу раздувать постоянную команду.",
      ]}
      relatedPages={[
        { href: "/for-clients", label: "Маршрут для заказчиков" },
        { href: "/hire/fastapi-backend", label: "FastAPI Backend" },
        { href: "/hire/nextjs-dashboard", label: "Next.js Dashboard" },
        { href: "/hire/urgent-bugfix", label: "Urgent Bugfix" },
      ]}
      leadCaptureSource="hire_mvp_sprint"
    />
  );
}