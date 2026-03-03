/**
 * Header с навигацией
 */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import NotificationBell from "@/components/layout/NotificationBell";

export default function Header() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  return (
    <header className="border-b border-amber-900/50 bg-black/80 backdrop-blur-md sticky top-0 z-50 shadow-[0_4px_20px_rgba(0,0,0,0.8)]">
      <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-amber-600 to-transparent opacity-50"></div>
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-2xl font-cinzel font-bold flex items-center gap-2 group">
            <span className="text-amber-500 drop-shadow-[0_0_8px_rgba(217,119,6,0.5)] group-hover:text-amber-400 transition-colors">⚡ Question</span>
            <span className="text-gray-300">Work</span>
          </Link>

          <nav className="flex items-center gap-8 font-cinzel uppercase tracking-widest text-sm">
            <Link
              href="/quests"
              className="text-gray-400 hover:text-amber-400 transition-colors relative group"
            >
              Доска заданий
              <span className="absolute -bottom-1 left-0 w-0 h-[1px] bg-amber-500 transition-all duration-300 group-hover:w-full"></span>
            </Link>
            <Link
              href="/marketplace"
              className="text-gray-400 hover:text-amber-400 transition-colors relative group"
            >
              Гильдия
              <span className="absolute -bottom-1 left-0 w-0 h-[1px] bg-amber-500 transition-all duration-300 group-hover:w-full"></span>
            </Link>
            {isAuthenticated && (
              <Link
                href="/quests/create"
                className="text-purple-400 hover:text-purple-300 transition-colors font-bold drop-shadow-[0_0_5px_rgba(168,85,247,0.5)] flex items-center gap-1"
              >
                + Создать контракт
              </Link>
            )}
          </nav>

          <div className="flex items-center gap-6">
            {isAuthenticated && user ? (
              <>
                <div className="scale-90 opacity-80 hover:opacity-100 hover:scale-100 transition-all">
                   <NotificationBell enabled={isAuthenticated} />
                </div>
                <div className="h-8 w-[1px] bg-gray-800"></div>
                <Link
                  href="/profile"
                  className="group flex items-center gap-3 hover:bg-gray-900/50 rounded p-1 pr-3 transition-colors border border-transparent hover:border-gray-800"
                >
                  <div className="avatar-frame w-10 h-10 shrink-0">
                    <div className="w-full h-full bg-gray-900 rounded-full flex items-center justify-center border-2 border-amber-900/50 group-hover:border-amber-500 transition-colors bg-gradient-to-br from-gray-800 to-black">
                      <span className="text-lg font-cinzel text-amber-500 font-bold group-hover:drop-shadow-[0_0_5px_rgba(217,119,6,0.8)]">
                        {user.username[0].toUpperCase()}
                      </span>
                    </div>
                  </div>

                  <div className="hidden sm:block text-left">
                    <div className="text-sm font-cinzel font-bold text-gray-200 group-hover:text-amber-100 transition-colors">
                      {user.username}
                    </div>
                    <div className="text-[10px] font-mono text-amber-600/80 uppercase tracking-widest">
                      Ур. {user.level} {user.grade}
                    </div>
                  </div>
                </Link>

                <button
                  onClick={handleLogout}
                  className="text-xs font-mono uppercase tracking-wider text-gray-500 hover:text-red-500 transition-colors"
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
          </div>
        </div>
      </div>
    </header>
  );
}
