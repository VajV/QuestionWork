import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import ErrorBoundary from "@/components/ui/ErrorBoundary";

export const metadata: Metadata = {
  title: "QuestionWork - IT Freelance RPG",
  description: "Биржа фриланса с геймификацией для IT-специалистов",
  icons: {
    icon: '/favicon.svg',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="bg-gray-950 text-white min-h-screen">
        <ErrorBoundary>
          <AuthProvider>
            {children}
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
