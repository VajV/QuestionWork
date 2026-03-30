import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        // 3-tier accent system
        gold: {
          DEFAULT: 'var(--accent-gold)',
          light: 'var(--accent-gold-light)',
          dim: 'var(--accent-gold-dim)',
        },
        purple: {
          DEFAULT: 'var(--accent-purple)',
          light: 'var(--accent-purple-light)',
          dim: 'var(--accent-purple-dim)',
        },
        cyan: {
          DEFAULT: 'var(--accent-cyan)',
          light: 'var(--accent-cyan-light)',
          dim: 'var(--accent-cyan-dim)',
        },
        // Rarity colors
        rarity: {
          novice: 'var(--rarity-novice)',
          junior: 'var(--rarity-junior)',
          middle: 'var(--rarity-middle)',
          senior: 'var(--rarity-senior)',
        },
        // Semantic
        success: 'var(--color-success)',
        danger: { DEFAULT: 'var(--color-danger)', dim: 'var(--color-danger-dim)' },
        warning: 'var(--color-warning)',
      },
      fontFamily: {
        cinzel: ['var(--font-cinzel)', 'serif'],
        inter: ['var(--font-inter)', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      },
      borderRadius: {
        'rpg-sm': 'var(--radius-sm)',
        'rpg-md': 'var(--radius-md)',
        'rpg-lg': 'var(--radius-lg)',
        'rpg-xl': 'var(--radius-xl)',
      },
      transitionTimingFunction: {
        'out-expo': 'var(--ease-out-expo)',
      },
      animation: {
        "neon-pulse": "neon-pulse 2s ease-in-out infinite",
        "rotate": "rotate 20s linear infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "xp-fill": "xp-fill 0.5s ease-out forwards",
        "shimmer": "shimmer 2.5s linear infinite",
        "hover-lift": "hover-lift 0.3s var(--ease-out-expo) forwards",
        "fade-in": "fade-in 0.5s var(--ease-out-expo) forwards",
        "slide-up": "slide-up 0.5s var(--ease-out-expo) forwards",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
      },
      keyframes: {
        "neon-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        "rotate": {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        "xp-fill": {
          from: { width: "0%" },
          to: { width: "100%" },
        },
        "shimmer": {
          from: { backgroundPosition: "-200% 0" },
          to: { backgroundPosition: "200% 0" },
        },
        "hover-lift": {
          to: { transform: "translateY(-2px)", boxShadow: "0 8px 30px rgba(0,0,0,0.3)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 8px var(--glow-gold)" },
          "50%": { boxShadow: "0 0 24px var(--glow-gold)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
