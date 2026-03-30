import type { Metadata } from "next";
import HireUseCaseTemplate from "@/components/marketing/HireUseCaseTemplate";

export const metadata: Metadata = {
  title: "Hire Urgent Bugfix Specialists | QuestionWork",
  description: "Наймите IT-специалиста для срочного bugfix, incident response и release recovery через понятный contracting flow.",
};

export default function HireUrgentBugfixPage() {
  return (
    <HireUseCaseTemplate
      eyebrow="Hire Use Case • Urgent Bugfix"
      title="Найм под срочный багфикс, инцидент и release recovery"
      description="Когда продукт уже падает, платёжный поток ломается или релиз нельзя выпускать без точечного ремонта, клиенту нужен быстрый вход без недельного пресейла."
      budgetBand="$300 - $1,500"
      recommendedQuestTemplate="Urgent production fix"
      outcomes={[
        "Быстро локализованный production issue с понятным owner и scope работ.",
        "Исправление критичного бага без попытки превращать инцидент в бесконечный discovery.",
        "Снижение business-impact за счёт короткого и жёстко ограниченного delivery window.",
        "Понятный follow-up: что исправлено сейчас и что нужно вынести в отдельный backlog после пожара.",
      ]}
      relatedPages={[
        { href: "/for-clients", label: "Маршрут для заказчиков" },
        { href: "/hire/fastapi-backend", label: "FastAPI Backend" },
        { href: "/hire/nextjs-dashboard", label: "Next.js Dashboard" },
        { href: "/hire/mvp-sprint", label: "MVP Sprint" },
      ]}
      leadCaptureSource="hire_urgent_bugfix"
    />
  );
}