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
        // Map rarity colors to tailwind config for utility usage
        rarity: {
          novice: 'var(--rarity-novice)',
          junior: 'var(--rarity-junior)',
          middle: 'var(--rarity-middle)',
          senior: 'var(--rarity-senior)',
        }
      },
      fontFamily: {
        cinzel: ['Cinzel', 'serif'],
        inter: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        "neon-pulse": "neon-pulse 2s ease-in-out infinite",
        "rotate": "rotate 20s linear infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "xp-fill": "xp-fill 0.5s ease-out forwards",
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
        }
      },
    },
  },
  plugins: [],
};
export default config;
