"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Users,
  ScrollText,
  Wallet,
  Activity,
  FileText,
  Menu,
  X,
  Shield,
  ChevronLeft,
  Gavel,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/admin/dashboard", label: "Дашборд", icon: LayoutDashboard },
  { href: "/admin/users", label: "Пользователи", icon: Users },
  { href: "/admin/quests", label: "Квесты", icon: ScrollText },
  { href: "/admin/withdrawals", label: "Выводы средств", icon: Wallet },
  { href: "/admin/disputes", label: "Споры", icon: Gavel },
  { href: "/admin/runtime", label: "Runtime", icon: Activity },
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
        className="lg:hidden fixed top-4 left-4 z-50 rounded-lg border border-sky-500/20 bg-slate-950/90 p-2 text-slate-300 backdrop-blur-md hover:border-sky-400/35 hover:text-sky-100"
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
          bg-[linear-gradient(180deg,rgba(2,6,23,0.98),rgba(9,14,23,0.96))] backdrop-blur-md
          border-r border-sky-500/10
          flex flex-col
          transition-transform duration-300
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
      >
        {/* Header */}
        <div className="border-b border-sky-500/10 p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="text-sky-300" size={22} />
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
          <p className="mt-1 text-[10px] font-mono uppercase tracking-widest text-sky-300/60">
            Ops Command Center
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
                      ? "border border-sky-400/30 bg-sky-500/12 text-sky-100 shadow-[0_0_12px_rgba(14,165,233,0.15)]"
                      : "border border-transparent text-slate-400 hover:bg-slate-900/80 hover:text-slate-100"
                  }
                `}
              >
                <Icon
                  size={18}
                  className={
                    isActive
                      ? "text-sky-300"
                      : "text-slate-500 group-hover:text-slate-300"
                  }
                />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-sky-500/10 p-4">
          <Link
            href="/"
            className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-slate-500 transition-colors hover:text-sky-200"
          >
            <ChevronLeft size={14} />
            На главную
          </Link>
        </div>
      </aside>
    </>
  );
}
