import type { Metadata } from "next";
import HireUseCaseTemplate from "@/components/marketing/HireUseCaseTemplate";

export const metadata: Metadata = {
  title: "Hire Next.js Dashboard Developers | QuestionWork",
  description: "Наймите Next.js специалиста для dashboard, internal tools и клиентских кабинетов через структурированный hiring flow.",
};

export default function HireNextJsDashboardPage() {
  return (
    <HireUseCaseTemplate
      eyebrow="Hire Use Case • Next.js Dashboard"
      title="Найм Next.js разработчика для dashboard и внутренних кабинетов"
      description="Этот вход нужен, когда клиенту надо быстро получить рабочий интерфейс: операционную панель, кабинет, reporting screen, admin workflow или аналитический дашборд."
      budgetBand="$700 - $2,500"
      recommendedQuestTemplate="Dashboard / internal tool build"
      outcomes={[
        "Собранный client-facing или internal dashboard с понятной навигацией и адаптивностью.",
        "Перенос разрозненной операционной логики в единый интерфейс для команды или клиента.",
        "Улучшение legibility данных без перегруза случайными UI-паттернами.",
        "Ускорение продуктового цикла там, где старый кабинет тормозит команду ежедневно.",
      ]}
      relatedPages={[
        { href: "/for-clients", label: "Маршрут для заказчиков" },
        { href: "/hire/fastapi-backend", label: "FastAPI Backend" },
        { href: "/hire/urgent-bugfix", label: "Urgent Bugfix" },
        { href: "/hire/mvp-sprint", label: "MVP Sprint" },
      ]}
      leadCaptureSource="hire_nextjs_dashboard"
    />
  );
}