# QuestionWork Frontend Setup Script
# Автоматическая настройка проекта

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Frontend Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$FRONTEND_ROOT = Split-Path -Parent $PSScriptRoot
$SRC_DIR = Join-Path $FRONTEND_ROOT "src"
$COMPONENTS_DIR = Join-Path $SRC_DIR "components"

Write-Host "`n[1/5] Создание структуры папок..." -ForegroundColor Yellow

# Создаём папки компонентов
$folders = @(
    (Join-Path $COMPONENTS_DIR "ui"),
    (Join-Path $COMPONENTS_DIR "layout"),
    (Join-Path $COMPONENTS_DIR "rpg"),
    (Join-Path $SRC_DIR "lib"),
    (Join-Path $SRC_DIR "types"),
    (Join-Path $SRC_DIR "store"),
    (Join-Path $SRC_DIR "hooks")
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "  + $folder" -ForegroundColor Green
    }
}

Write-Host "`n[2/5] Создание файлов компонентов..." -ForegroundColor Yellow

# ============================================
# globals.css
# ============================================
$globalsCss = @'
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #0f0f1a;
  --foreground: #e0e0e0;
  --accent: #8b5cf6;
  --accent-glow: rgba(139, 92, 246, 0.5);
}

* {
  box-sizing: border-box;
  padding: 0;
  margin: 0;
}

html,
body {
  max-width: 100vw;
  overflow-x: hidden;
  background: var(--background);
  color: var(--foreground);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* RPG Scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #1a1a2e;
}

::-webkit-scrollbar-thumb {
  background: #4c1d95;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #6d28d9;
}

/* Glow effect */
.glow {
  box-shadow: 0 0 20px var(--accent-glow);
}

.glow-text {
  text-shadow: 0 0 10px var(--accent-glow);
}
'@

$globalsPath = Join-Path $SRC_DIR "app\globals.css"
$globalsCss | Out-File -FilePath $globalsPath -Encoding UTF8 -Force
Write-Host "  + app/globals.css" -ForegroundColor Green

# ============================================
# layout.tsx
# ============================================
$layoutTs = @'
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuestionWork - IT Freelance Marketplace",
  description: "Биржа фриланса с RPG-геймификацией для IT-специалистов",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="bg-gray-900 text-white min-h-screen">
        {children}
      </body>
    </html>
  );
}
'@

$layoutPath = Join-Path $SRC_DIR "app\layout.tsx"
$layoutTs | Out-File -FilePath $layoutPath -Encoding UTF8 -Force
Write-Host "  + app/layout.tsx" -ForegroundColor Green

# ============================================
# page.tsx (RPG Profile)
# ============================================
$pageTs = @'
"use client";

import { motion } from "framer-motion";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

// Типы для профиля
interface Profile {
  username: string;
  level: number;
  grade: string;
  xp: number;
  maxXp: number;
  stats: {
    int: number;
    dex: number;
    cha: number;
  };
}

// Демо-данные (позже будут приходить с бэкенда)
const demoProfile: Profile = {
  username: "NoviceDev",
  level: 1,
  grade: "Novice",
  xp: 0,
  maxXp: 100,
  stats: {
    int: 10,
    dex: 10,
    cha: 10,
  },
};

export default function Home() {
  const profile = demoProfile;
  const xpPercent = (profile.xp / profile.maxXp) * 100;

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-4xl mx-auto"
        >
          {/* Заголовок */}
          <h1 className="text-4xl font-bold text-center mb-8 glow-text">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </h1>

          {/* Профиль */}
          <Card className="p-6 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-center">
              {/* Аватар */}
              <div className="relative">
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-4xl font-bold glow">
                  {profile.username[0]}
                </div>
                <div className="absolute -bottom-2 -right-2">
                  <LevelBadge level={profile.level} grade={profile.grade} />
                </div>
              </div>

              {/* Инфо */}
              <div className="flex-1 w-full">
                <h2 className="text-2xl font-bold mb-2">{profile.username}</h2>
                <p className="text-gray-400 mb-4">IT Freelancer</p>
                
                {/* XP Bar */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-purple-300">Experience</span>
                    <span className="text-purple-300">{profile.xp} / {profile.maxXp} XP</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-4 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${xpPercent}%` }}
                      transition={{ duration: 1, delay: 0.3 }}
                      className="h-full bg-gradient-to-r from-purple-600 to-purple-400"
                    />
                  </div>
                </div>

                {/* Кнопка */}
                <Button disabled variant="primary">
                  🔒 Начать квест (скоро)
                </Button>
              </div>
            </div>
          </Card>

          {/* Статы */}
          <StatsPanel stats={profile.stats} />
        </motion.div>
      </div>
    </main>
  );
}
'@

$pagePath = Join-Path $SRC_DIR "app\page.tsx"
$pageTs | Out-File -FilePath $pagePath -Encoding UTF8 -Force
Write-Host "  + app/page.tsx" -ForegroundColor Green

# ============================================
# Button.tsx
# ============================================
$buttonTs = @'
import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  className?: string;
}

export default function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = '',
}: ButtonProps) {
  const baseStyles = 'px-4 py-2 rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95';
  
  const variantStyles = {
    primary: 'bg-purple-600 hover:bg-purple-700 text-white shadow-lg shadow-purple-500/30',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-white',
    danger: 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/30',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
'@

$buttonPath = Join-Path $COMPONENTS_DIR "ui\Button.tsx"
$buttonTs | Out-File -FilePath $buttonPath -Encoding UTF8 -Force
Write-Host "  + components/ui/Button.tsx" -ForegroundColor Green

# ============================================
# ProgressBar.tsx
# ============================================
$progressBarTs = @'
"use client";

import { motion } from "framer-motion";

interface ProgressBarProps {
  value: number;
  max: number;
  label?: string;
  color?: 'purple' | 'green' | 'blue' | 'red';
  showPercent?: boolean;
  className?: string;
}

export default function ProgressBar({
  value,
  max,
  label,
  color = 'purple',
  showPercent = true,
  className = '',
}: ProgressBarProps) {
  const percent = Math.min((value / max) * 100, 100);
  
  const colorStyles = {
    purple: 'from-purple-600 to-purple-400 shadow-purple-500/30',
    green: 'from-green-600 to-green-400 shadow-green-500/30',
    blue: 'from-blue-600 to-blue-400 shadow-blue-500/30',
    red: 'from-red-600 to-red-400 shadow-red-500/30',
  };

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercent) && (
        <div className="flex justify-between text-sm mb-1">
          {label && <span className="text-gray-300">{label}</span>}
          {showPercent && (
            <span className="text-gray-300">{Math.round(percent)}%</span>
          )}
        </div>
      )}
      <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={`h-full bg-gradient-to-r ${colorStyles[color]} shadow-lg`}
        />
      </div>
    </div>
  );
}
'@

$progressBarPath = Join-Path $COMPONENTS_DIR "ui\ProgressBar.tsx"
$progressBarTs | Out-File -FilePath $progressBarPath -Encoding UTF8 -Force
Write-Host "  + components/ui/ProgressBar.tsx" -ForegroundColor Green

# ============================================
# Card.tsx
# ============================================
$cardTs = @'
import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export default function Card({ children, className = '', hover = false }: CardProps) {
  const baseStyles = 'bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-4';
  const hoverStyles = hover ? 'hover:border-purple-500/50 hover:shadow-lg hover:shadow-purple-500/10 transition-all duration-300' : '';

  return (
    <div className={`${baseStyles} ${hoverStyles} ${className}`}>
      {children}
    </div>
  );
}
'@

$cardPath = Join-Path $COMPONENTS_DIR "ui\Card.tsx"
$cardTs | Out-File -FilePath $cardPath -Encoding UTF8 -Force
Write-Host "  + components/ui/Card.tsx" -ForegroundColor Green

# ============================================
# Header.tsx
# ============================================
$headerTs = @'
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
'@

$headerPath = Join-Path $COMPONENTS_DIR "layout\Header.tsx"
$headerTs | Out-File -FilePath $headerPath -Encoding UTF8 -Force
Write-Host "  + components/layout/Header.tsx" -ForegroundColor Green

# ============================================
# LevelBadge.tsx
# ============================================
$levelBadgeTs = @'
interface LevelBadgeProps {
  level: number;
  grade: string;
  size?: 'sm' | 'md' | 'lg';
}

const gradeColors = {
  Novice: 'from-gray-500 to-gray-700',
  Junior: 'from-green-500 to-green-700',
  Middle: 'from-blue-500 to-blue-700',
  Senior: 'from-purple-500 to-purple-700',
};

export default function LevelBadge({ level, grade, size = 'md' }: LevelBadgeProps) {
  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  };

  const gradient = gradeColors[grade as keyof typeof gradeColors] || gradeColors.Novice;

  return (
    <div className={`bg-gradient-to-r ${gradient} ${sizeStyles[size]} rounded-full font-bold shadow-lg`}>
      Lv.{level} {grade}
    </div>
  );
}
'@

$levelBadgePath = Join-Path $COMPONENTS_DIR "rpg\LevelBadge.tsx"
$levelBadgeTs | Out-File -FilePath $levelBadgePath -Encoding UTF8 -Force
Write-Host "  + components/rpg/LevelBadge.tsx" -ForegroundColor Green

# ============================================
# StatsPanel.tsx
# ============================================
$statsPanelTs = @'
"use client";

import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";

interface Stats {
  int: number;
  dex: number;
  cha: number;
}

interface StatsPanelProps {
  stats: Stats;
}

const statIcons = {
  int: '🧠',
  dex: '⚡',
  cha: '💬',
};

const statNames = {
  int: 'Интеллект',
  dex: 'Ловкость',
  cha: 'Харизма',
};

const statColors = {
  int: 'blue' as const,
  dex: 'green' as const,
  cha: 'purple' as const,
};

export default function StatsPanel({ stats }: StatsPanelProps) {
  // Максимальный стат для расчёта процента (база = 10)
  const maxStat = 20;

  return (
    <Card className="p-6">
      <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>📊</span> Характеристики
      </h3>
      
      <div className="space-y-4">
        {(Object.keys(stats) as Array<keyof Stats>).map((statKey) => (
          <div key={statKey}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xl">{statIcons[statKey]}</span>
              <span className="text-gray-300 flex-1">{statNames[statKey]}</span>
              <span className="text-white font-bold">{stats[statKey]}</span>
            </div>
            <ProgressBar
              value={stats[statKey]}
              max={maxStat}
              showPercent={false}
              color={statColors[statKey]}
            />
          </div>
        ))}
      </div>

      {/* Подсказка */}
      <p className="text-gray-500 text-sm mt-4">
        💡 Статы растут с выполнением квестов и повышением уровня
      </p>
    </Card>
  );
}
'@

$statsPanelPath = Join-Path $COMPONENTS_DIR "rpg\StatsPanel.tsx"
$statsPanelTs | Out-File -FilePath $statsPanelPath -Encoding UTF8 -Force
Write-Host "  + components/rpg/StatsPanel.tsx" -ForegroundColor Green

Write-Host "`n[3/5] Проверка зависимостей npm..." -ForegroundColor Yellow

# Проверяем, установлен ли framer-motion
$packageJsonPath = Join-Path $FRONTEND_ROOT "package.json"
$packageJson = Get-Content $packageJsonPath -Raw | ConvertFrom-Json

if (-not $packageJson.dependencies.'framer-motion') {
    Write-Host "  Установка framer-motion..." -ForegroundColor Yellow
    Set-Location $FRONTEND_ROOT
    npm install framer-motion
} else {
    Write-Host "  framer-motion уже установлен" -ForegroundColor Green
}

Write-Host "`n[4/5] Создание run.ps1 скрипта..." -ForegroundColor Yellow

$runScript = @'
# QuestionWork Frontend Run Script
# Запуск dev сервера

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Dev Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$FRONTEND_ROOT = Split-Path -Parent $PSScriptRoot

Set-Location $FRONTEND_ROOT

Write-Host "`nЗапуск Next.js dev сервера..." -ForegroundColor Yellow
Write-Host "Открой браузер: http://localhost:3001" -ForegroundColor Green
Write-Host "`nНажми Ctrl+C для остановки`n" -ForegroundColor Gray

npm run dev
'@

$runScriptPath = Join-Path $FRONTEND_ROOT "scripts\run.ps1"
if (-not (Test-Path (Split-Path $runScriptPath))) {
    New-Item -ItemType Directory -Path (Split-Path $runScriptPath) -Force | Out-Null
}
$runScript | Out-File -FilePath $runScriptPath -Encoding UTF8 -Force
Write-Host "  + scripts/run.ps1" -ForegroundColor Green

Write-Host "`n[5/5] Настройка завершена!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n✅ Готово! Для запуска проекта:" -ForegroundColor Green
Write-Host "   1. Перейди в C:\QuestionWork\frontend" -ForegroundColor White
Write-Host "   2. Запусти: .\scripts\run.ps1" -ForegroundColor White
Write-Host "   3. Открой http://localhost:3001" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
