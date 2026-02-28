"use client";

import Link from "next/link";

export default function Header() {
  return (
    <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Логотип */}
          <Link href="/" className="text-2xl font-bold">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </Link>

          {/* Навигация */}
          <nav className="flex items-center gap-6">
            <Link href="/quests" className="text-gray-400 hover:text-white transition-colors">
              Квесты
            </Link>
            <Link href="/marketplace" className="text-gray-400 hover:text-white transition-colors">
              Биржа
            </Link>
            <Link href="/profile" className="text-gray-400 hover:text-white transition-colors">
              Профиль
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
