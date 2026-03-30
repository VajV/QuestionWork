import type { Metadata } from "next";
import HireUseCaseTemplate from "@/components/marketing/HireUseCaseTemplate";

export const metadata: Metadata = {
  title: "Hire FastAPI Backend Specialists | QuestionWork",
  description: "Наймите FastAPI backend-специалиста для API, async workflows, PostgreSQL и production hardening через client-first hiring flow.",
};

export default function HireFastApiBackendPage() {
  return (
    <HireUseCaseTemplate
      eyebrow="Hire Use Case • FastAPI Backend"
      title="Найм FastAPI backend-специалиста под API и production delivery"
      description="Подходит, когда клиенту нужно быстро собрать или стабилизировать backend: API-слой, auth, database flows, background jobs, админку или интеграции."
      budgetBand="$800 - $3,000"
      recommendedQuestTemplate="Backend API / integration sprint"
      outcomes={[
        "Собранный или переработанный API-слой под конкретный продуктовый поток.",
        "Приведённые к боевому состоянию auth, validation, async jobs и database queries.",
        "Понятная зона ответственности по backend delivery и ручкам, которые реально нужны бизнесу.",
        "Снижение риска перед релизом или интеграцией с внешними системами.",
      ]}
      relatedPages={[
        { href: "/for-clients", label: "Маршрут для заказчиков" },
        { href: "/hire/nextjs-dashboard", label: "Next.js Dashboard" },
        { href: "/hire/urgent-bugfix", label: "Urgent Bugfix" },
        { href: "/hire/mvp-sprint", label: "MVP Sprint" },
      ]}
      leadCaptureSource="hire_fastapi_backend"
    />
  );
}