"use client";

import { useEffect } from "react";
import { AnimatePresence, LazyMotion, motion, useReducedMotion, domAnimation } from "@/lib/motion";
import { usePathname } from "next/navigation";
import { AuthProvider } from "@/context/AuthContext";
import { WorldMetaProvider } from "@/context/WorldMetaContext";
import ErrorBoundary from "@/components/ui/ErrorBoundary";
import { persistAttributionFromLocation } from "@/lib/attribution";

interface ClientAppShellProps {
  children: React.ReactNode;
}

export default function ClientAppShell({ children }: ClientAppShellProps) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    async function cleanupDevServiceWorker() {
      if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
        return;
      }

      const isLocalhost =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1";

      if (!isLocalhost) {
        return;
      }

      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((registration) => registration.unregister()));

        if ("caches" in window) {
          const keys = await caches.keys();
          await Promise.all(
            keys
              .filter((key) => key.startsWith("qwork"))
              .map((key) => caches.delete(key)),
          );
        }
      } catch (error) {
        console.error("Failed to cleanup local service worker:", error);
      }
    }

    void cleanupDevServiceWorker();
  }, []);

  useEffect(() => {
    persistAttributionFromLocation();
  }, [pathname]);

  return (
    <ErrorBoundary>
      <AuthProvider>
        <WorldMetaProvider>
          <LazyMotion features={domAnimation}>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={pathname}
                initial={reduceMotion ? false : { opacity: 0, y: 18, filter: "blur(10px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={reduceMotion ? { opacity: 1, y: 0, filter: "blur(0px)" } : { opacity: 0, y: -10, filter: "blur(8px)" }}
                transition={{ duration: reduceMotion ? 0.01 : 0.28, ease: [0.22, 1, 0.36, 1] }}
              >
                {children}
              </motion.div>
            </AnimatePresence>
          </LazyMotion>
        </WorldMetaProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}
