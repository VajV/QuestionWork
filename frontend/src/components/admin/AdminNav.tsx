"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Users,
  ScrollText,
  Wallet,
  FileText,
  Menu,
  X,
  Shield,
  ChevronLeft,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/admin/dashboard", label: "Дашборд", icon: LayoutDashboard },
  { href: "/admin/users", label: "Пользователи", icon: Users },
  { href: "/admin/quests", label: "Квесты", icon: ScrollText },
  { href: "/admin/withdrawals", label: "Выводы средств", icon: Wallet },
  { href: "/admin/logs", label: "Аудит логи", icon: FileText },
] as const;

export default function AdminNav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-gray-900/90 border border-gray-700 rounded-lg text-gray-300 hover:text-white backdrop-blur-md"
        aria-label="Открыть меню"
      >
        <Menu size={20} />
      </button>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/60 z-40 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:sticky top-0 left-0 z-50 lg:z-auto
          h-screen w-64 shrink-0
          bg-gray-950/95 backdrop-blur-md
          border-r border-gray-800
          flex flex-col
          transition-transform duration-300
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
      >
        {/* Header */}
        <div className="p-5 border-b border-gray-800/80">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="text-purple-400" size={22} />
              <span className="font-cinzel font-bold text-lg text-white tracking-wide">
                Админ
              </span>
            </div>
            <button
              onClick={() => setMobileOpen(false)}
              className="lg:hidden text-gray-500 hover:text-white"
            >
              <X size={18} />
            </button>
          </div>
          <p className="text-[10px] font-mono text-purple-500/70 mt-1 uppercase tracking-widest">
            QuestionWork Panel
          </p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                  transition-all duration-200 group
                  ${
                    isActive
                      ? "bg-purple-600/20 text-purple-300 border border-purple-500/30 shadow-[0_0_12px_rgba(168,85,247,0.15)]"
                      : "text-gray-400 hover:text-white hover:bg-gray-800/60 border border-transparent"
                  }
                `}
              >
                <Icon
                  size={18}
                  className={
                    isActive
                      ? "text-purple-400"
                      : "text-gray-500 group-hover:text-gray-300"
                  }
                />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-800/80">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-amber-400 transition-colors font-mono uppercase tracking-wider"
          >
            <ChevronLeft size={14} />
            На главную
          </Link>
        </div>
      </aside>
    </>
  );
}
