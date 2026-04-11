import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import ClientAppShell from "@/components/ui/ClientAppShell";

export const metadata: Metadata = {
  title: "QuestionWork | Найм IT-специалистов и исполнение контрактов",
  description: "Наймите FastAPI, Next.js и full-stack специалистов, проведите задачу через понятный контрактный поток и доведите работу до подтверждённой сдачи.",
  openGraph: {
    title: "QuestionWork | Найм IT-специалистов и исполнение контрактов",
    description: "Клиентский путь для найма IT-специалистов: от брифа и отбора до безопасного исполнения контракта.",
    siteName: "QuestionWork",
    locale: "ru_RU",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <Script src="/sw-cleanup.js" strategy="beforeInteractive" />
      </head>
      <body className="bg-gray-950 text-white min-h-screen" suppressHydrationWarning>
        <ClientAppShell>
          {children}
        </ClientAppShell>
      </body>
    </html>
  );
}
