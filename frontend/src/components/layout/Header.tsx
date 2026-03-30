/**
 * Header с навигацией
 */

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import NotificationBell from "@/components/layout/NotificationBell";
import { getXpDisplay } from "@/lib/xp";
import { Menu, Shield, X } from "lucide-react";

function navLinkClass(isActive: boolean) {
  return `group relative transition-colors duration-300 ${
    isActive
      ? "text-amber-300 drop-shadow-[0_0_6px_rgba(251,191,36,0.4)]"
      : "text-gray-400 hover:text-amber-400"
  }`;
}

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const xpDisplay = user ? getXpDisplay(user.xp ?? 0, user.xp_to_next ?? 0) : null;
  const [mobileOpen, setMobileOpen] = useState(false);
  const canCreateContracts = isAuthenticated && (user?.role === "client" || user?.role === "admin");

  const navItems = useMemo(
    () => [
      { href: "/for-clients", label: "Для заказчиков" },
      { href: "/quests", label: "Доска заданий" },
      { href: "/marketplace", label: "Гильдия" },
      { href: "/events", label: "Ивенты" },
      { href: "/learning", label: "Обучение" },
      ...(isAuthenticated ? [{ href: "/messages", label: "Диалоги" }] : []),
    ],
    [isAuthenticated],
  );

  const handleLogout = async () => {
    await logout();
    setMobileOpen(false);
    router.push("/");
  };

  return (
    <>
      {/* L-04: Skip-to-main-content for accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded focus:bg-amber-700 focus:px-4 focus:py-2 focus:text-white focus:outline-none"
      >
        Перейти к содержимому
      </a>
      <header className="border-b border-amber-900/50 bg-black/80 backdrop-blur-md sticky top-0 z-50 shadow-[0_4px_20px_rgba(0,0,0,0.8)]">
      <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-amber-600 to-transparent opacity-50"></div>
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-1.5 whitespace-nowrap font-cinzel text-[1.9rem] font-bold leading-none group sm:text-[2.2rem] lg:text-[1.6rem] xl:text-[2rem]"
          >
            <span className="text-amber-500 drop-shadow-[0_0_10px_rgba(217,119,6,0.55)] transition-colors group-hover:text-amber-400">⚡ Question</span>
            <span className="text-gray-300 drop-shadow-[0_0_12px_rgba(255,255,255,0.08)]">Work</span>
          </Link>

          <nav className="hidden items-center gap-3 font-cinzel uppercase tracking-wide text-xs lg:flex xl:gap-5 xl:text-sm xl:tracking-widest">
            {navItems.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={navLinkClass(isActive)}
                >
                  {item.label}
                  <span
                    className={`absolute -bottom-1 left-0 h-[2px] rounded-full transition-all duration-300 ${
                      isActive
                        ? "w-full bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 shadow-[0_0_8px_var(--glow-gold)]"
                        : "w-0 bg-amber-500 group-hover:w-full"
                    }`}
                  />
                </Link>
              );
            })}
            {canCreateContracts && (
              <Link
                href="/quests/create"
                className="text-purple-400 hover:text-purple-300 transition-colors font-bold drop-shadow-[0_0_5px_rgba(168,85,247,0.5)] flex items-center gap-1"
              >
                + Создать контракт
              </Link>
            )}
            {isAuthenticated && user?.role === "admin" && (
              <Link
                href="/admin/dashboard"
                className="text-purple-400 hover:text-purple-300 transition-colors font-bold drop-shadow-[0_0_5px_rgba(168,85,247,0.5)] flex items-center gap-1"
              >
                <Shield size={14} />
                Админ
              </Link>
            )}
          </nav>

          <div className="flex items-center gap-3 md:gap-6">
            {isAuthenticated && user ? (
              <>
                <div className="scale-90 opacity-80 hover:opacity-100 hover:scale-100 transition-all">
                   <NotificationBell enabled={isAuthenticated} />
                </div>
                <div className="hidden h-8 w-[1px] bg-gray-800 md:block"></div>
                <Link
                  href="/profile"
                  className="group flex items-center gap-3 hover:bg-gray-900/50 rounded-lg p-1.5 pr-2 md:pr-3 transition-all duration-300 border border-transparent hover:border-amber-900/30 hover:shadow-[0_0_12px_rgba(217,119,6,0.1)]"
                >
                  <div className="relative w-10 h-10 shrink-0">
                    <div className="w-full h-full bg-gray-900 rounded-full flex items-center justify-center border-2 border-amber-900/50 group-hover:border-amber-500 transition-colors bg-gradient-to-br from-gray-800 to-black">
                      <span className="text-lg font-cinzel text-amber-500 font-bold group-hover:drop-shadow-[0_0_5px_rgba(217,119,6,0.8)]">
                        {user.username[0].toUpperCase()}
                      </span>
                    </div>
                    {/* Level badge */}
                    <span className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-gray-950 border border-amber-700/60 text-[9px] font-mono font-bold text-amber-400">
                      {user.level}
                    </span>
                  </div>

                  <div className="hidden md:flex flex-col gap-0.5 text-left">
                    <div className="text-sm font-cinzel font-bold text-gray-200 group-hover:text-amber-100 transition-colors leading-tight">
                      {user.username}
                    </div>
                    <div className="text-[10px] font-mono text-amber-600/80 uppercase tracking-widest leading-tight">
                      {user.grade}
                    </div>
                    {/* Mini XP progress bar */}
                    <div className="w-20 h-[3px] rounded-full bg-gray-800 mt-0.5 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-purple-600 to-purple-400"
                        style={{ width: `${xpDisplay?.percent ?? 100}%` }}
                      />
                    </div>
                  </div>
                </Link>

                <button
                  onClick={handleLogout}
                  className="text-xs font-mono uppercase tracking-wider text-gray-500 hover:text-red-500 transition-colors shrink-0"
                  title="Покинуть гильдию"
                >
                  Выйти
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/auth/login"
                  className="text-gray-400 hover:text-white font-cinzel uppercase tracking-wider text-sm transition-colors"
                >
                  Войти
                </Link>
                <Link
                  href="/auth/register"
                  className="bg-gradient-to-r from-amber-800 to-amber-950 hover:from-amber-700 hover:to-amber-900 text-white px-5 py-2 rounded font-cinzel font-bold uppercase tracking-widest text-xs transition-all border border-amber-600/50 shadow-[0_0_15px_rgba(217,119,6,0.2)] hover:shadow-[0_0_20px_rgba(217,119,6,0.4)]"
                >
                  Примкнуть
                </Link>
              </>
            )}

            <button
              type="button"
              onClick={() => setMobileOpen((prev) => !prev)}
              className="inline-flex rounded-lg border border-gray-800 p-2 text-gray-300 transition-colors hover:border-amber-500/40 hover:text-amber-300 lg:hidden"
              aria-label={mobileOpen ? "Закрыть меню" : "Открыть меню"}
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-950/95 p-4 lg:hidden">
            <nav className="flex flex-col gap-2 font-cinzel uppercase tracking-widest text-xs">
              {navItems.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={`rounded-xl border px-4 py-3 ${
                      isActive
                        ? "border-amber-500/40 bg-amber-900/20 text-amber-300"
                        : "border-gray-800 bg-black/20 text-gray-400"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}

              {canCreateContracts && (
                <Link
                  href="/quests/create"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-xl border border-purple-500/30 bg-purple-900/20 px-4 py-3 text-purple-300"
                >
                  + Создать контракт
                </Link>
              )}

              {isAuthenticated && user?.role === "admin" && (
                <Link
                  href="/admin/dashboard"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-xl border border-purple-500/30 bg-purple-900/20 px-4 py-3 text-purple-300"
                >
                  Админ
                </Link>
              )}

              {isAuthenticated && (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-xl border border-red-500/20 bg-red-950/10 px-4 py-3 text-left text-red-300"
                >
                  Выйти
                </button>
              )}
            </nav>
          </div>
        )}
      </div>
    </header>
    </>
  );
}
