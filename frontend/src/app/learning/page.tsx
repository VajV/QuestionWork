import type { Metadata } from "next";
import LearningContent from "./LearningContent";

export const metadata: Metadata = {
  title: "Обучение — QuestionWork",
  description: "Прокачай навыки: разговорные языки, нейросети и языки программирования",
};

export default function LearningPage() {
  return <LearningContent />;
}