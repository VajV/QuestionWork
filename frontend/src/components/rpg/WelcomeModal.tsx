"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Swords, ChevronRight, X } from "lucide-react";

interface WelcomeModalProps {
  isOpen: boolean;
  username: string;
  userLevel: number;
  onSelectClass: () => void;
  onClose: () => void;
}

export default function WelcomeModal({
  isOpen,
  username,
  userLevel,
  onSelectClass,
  onClose,
}: WelcomeModalProps) {
  if (!isOpen) return null;

  const canPickClass = userLevel >= 5;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />

        <motion.div
          className="relative w-full max-w-lg bg-gray-900 border border-purple-700/50 rounded-2xl shadow-2xl overflow-hidden"
          initial={{ scale: 0.85, y: 30 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.85, y: 30 }}
          transition={{ type: "spring", stiffness: 350, damping: 30 }}
        >
          {/* Ambient glow */}
          <div className="absolute -top-20 -right-20 w-60 h-60 rounded-full bg-purple-500 blur-[100px] opacity-20 pointer-events-none" />
          <div className="absolute -bottom-16 -left-16 w-48 h-48 rounded-full bg-amber-500 blur-[80px] opacity-15 pointer-events-none" />

          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1 text-gray-500 hover:text-white transition-colors z-20"
          >
            <X size={20} />
          </button>

          <div className="relative z-10 p-8 text-center space-y-6">
            {/* Icon */}
            <motion.div
              initial={{ rotate: -10, scale: 0.8 }}
              animate={{ rotate: 0, scale: 1 }}
              transition={{ delay: 0.2, type: "spring" }}
            >
              <Swords className="mx-auto text-amber-500" size={56} />
            </motion.div>

            {/* Title */}
            <div>
              <h2 className="text-2xl font-cinzel font-bold text-white mb-2">
                Добро пожаловать, <span className="text-amber-400">{username}</span>!
              </h2>
              <p className="text-gray-400 text-sm leading-relaxed">
                Вы вступили в Гильдию Разработчиков. Берите квесты, зарабатывайте XP и золото,
                прокачивайте персонажа от <span className="text-green-400">Novice</span> до{" "}
                <span className="text-purple-400">Senior</span>.
              </p>
            </div>

            {/* Steps */}
            <div className="text-left space-y-3">
              {[
                { icon: "📜", text: "Выбирайте квесты на бирже" },
                { icon: "⚔️", text: "Выполняйте задачи и получайте XP" },
                { icon: "🛡️", text: "Выберите класс на уровне 5" },
                { icon: "🏆", text: "Собирайте бейджи и открывайте перки" },
              ].map((s, i) => (
                <motion.div
                  key={i}
                  className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-800/50"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.1 }}
                >
                  <span className="text-xl">{s.icon}</span>
                  <span className="text-sm text-gray-300">{s.text}</span>
                </motion.div>
              ))}
            </div>

            {/* CTA */}
            <div className="flex flex-col gap-2 pt-2">
              {canPickClass ? (
                <button
                  onClick={onSelectClass}
                  className="w-full py-3 rounded-lg bg-gradient-to-r from-amber-600 to-amber-800 text-white font-cinzel font-bold shadow-[0_0_20px_rgba(217,119,6,0.4)] hover:shadow-[0_0_30px_rgba(217,119,6,0.6)] transition-shadow flex items-center justify-center gap-2"
                >
                  <Sparkles size={18} /> Выбрать класс
                </button>
              ) : (
                <button
                  onClick={onClose}
                  className="w-full py-3 rounded-lg bg-gradient-to-r from-purple-600 to-purple-800 text-white font-cinzel font-bold shadow-[0_0_20px_rgba(168,85,247,0.3)] hover:shadow-[0_0_30px_rgba(168,85,247,0.5)] transition-shadow flex items-center justify-center gap-2"
                >
                  <ChevronRight size={18} /> Начать приключение
                </button>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
