import React from 'react';

type CardVariant = 'default' | 'hero' | 'data' | 'activity' | 'quest' | 'stat';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  variant?: CardVariant;
  as?: 'div' | 'section' | 'article';
  glow?: 'gold' | 'purple' | 'cyan' | 'none';
}

const variantStyles: Record<CardVariant, string> = {
  default: 'rpg-card p-6',
  hero: 'rpg-card p-8 border-amber-500/30 bg-gradient-to-br from-[var(--bg-card)] to-[var(--bg-secondary)]',
  data: 'rpg-card p-5 border-[var(--border-subtle)]',
  activity: 'rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] p-4',
  quest: 'rpg-card p-5 border-purple-500/20 bg-gradient-to-br from-[var(--bg-card)] via-[var(--bg-card)] to-purple-950/10',
  stat: 'rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] p-4 text-center',
};

const glowMap: Record<string, string> = {
  gold: 'shadow-[0_0_20px_var(--glow-gold)]',
  purple: 'shadow-[0_0_20px_var(--glow-purple)]',
  cyan: 'shadow-[0_0_20px_var(--glow-cyan)]',
  none: '',
};

export default function Card({
  children,
  className = '',
  hover = false,
  variant = 'default',
  as: Tag = 'div',
  glow = 'none',
}: CardProps) {
  const hoverStyles = hover
    ? 'hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(217,119,6,0.3)] transition-all duration-300 cursor-pointer'
    : 'transition-all duration-300';

  return (
    <Tag className={`${variantStyles[variant]} ${glowMap[glow]} ${hoverStyles} ${className}`}>
      {children}
    </Tag>
  );
}
