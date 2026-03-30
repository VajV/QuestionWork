import React from 'react';
import Link from 'next/link';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'rpg-special';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
  loading?: boolean;
  loadingLabel?: string;
  /**
   * When provided the button renders as a Next.js <Link> (i.e. an <a> element)
   * instead of a <button>. Use this instead of wrapping <Button> in <Link> to
   * avoid invalid <a><button></button></a> HTML that causes hydration errors.
   */
  href?: string;
}

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-4 py-1.5 text-xs',
  md: 'px-6 py-2.5 text-sm',
  lg: 'px-8 py-3.5 text-base',
};

export default function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  loading = false,
  loadingLabel = 'Загрузка…',
  href,
}: ButtonProps) {
  const baseStyles = 'rounded font-cinzel font-bold uppercase tracking-widest transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 hover:scale-105 active:scale-95 flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950';

  const variantStyles: Record<ButtonVariant, string> = {
    primary: 'bg-gradient-to-r from-amber-700 to-amber-900 text-white border border-amber-500/50 shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:from-amber-600 hover:to-amber-800 hover:shadow-[0_0_20px_rgba(217,119,6,0.5)]',
    secondary: 'bg-gray-900/80 text-gray-300 border border-gray-600/50 shadow-[0_0_10px_rgba(0,0,0,0.5)] hover:bg-gray-800 hover:text-white hover:border-gray-500 hover:shadow-[0_0_15px_rgba(156,163,175,0.2)]',
    danger: 'bg-gradient-to-r from-red-900 to-red-950 text-red-100 border border-red-700/70 shadow-[0_0_15px_rgba(220,38,38,0.3)] hover:from-red-800 hover:to-red-900 hover:shadow-[0_0_20px_rgba(220,38,38,0.5)]',
    ghost: 'bg-transparent text-gray-400 border border-transparent hover:text-white hover:bg-white/5 hover:border-white/10',
    'rpg-special': 'bg-gradient-to-r from-amber-600 via-yellow-500 to-amber-600 text-gray-950 border border-yellow-400/60 shadow-[0_0_20px_var(--glow-gold)] hover:shadow-[0_0_35px_var(--glow-gold)] animate-pulse-glow',
  };

  const combinedClass = `${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`;

  if (href) {
    return (
      <Link href={href} className={combinedClass}>
        {children}
      </Link>
    );
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={combinedClass}
      aria-busy={loading || undefined}
    >
      {loading ? (
        <>
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          {loadingLabel}
        </>
      ) : (
        children
      )}
    </button>
  );
}
