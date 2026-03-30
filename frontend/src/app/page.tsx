import type { Metadata } from "next";
import HomeClientSection from "@/components/home/HomeClientSection";

export const metadata: Metadata = {
  title: "QuestionWork — IT Freelance Marketplace with RPG Progression",
  description:
    "Наймите IT-исполнителя без хаоса: FastAPI backend, Next.js dashboards, срочные багфиксы. Структурированный процесс, escrow, RPG-прогрессия.",
  openGraph: {
    title: "QuestionWork — IT Freelance Marketplace",
    description:
      "Платформа для найма IT-специалистов с понятным контрактным потоком и RPG-геймификацией.",
    type: "website",
  },
};

export default function Home() {
  return <HomeClientSection />;
}
