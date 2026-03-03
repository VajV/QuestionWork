import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  className?: string;
  type?: 'button' | 'submit' | 'reset';
}

export default function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = '',
  type = 'button',
}: ButtonProps) {
  const baseStyles = 'px-6 py-2.5 rounded font-cinzel font-bold uppercase tracking-widest transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 hover:scale-105 active:scale-95 flex items-center justify-center gap-2';

  const variantStyles = {
    primary: 'bg-gradient-to-r from-amber-700 to-amber-900 text-white border border-amber-500/50 shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:from-amber-600 hover:to-amber-800 hover:shadow-[0_0_20px_rgba(217,119,6,0.5)]',
    secondary: 'bg-gray-900/80 text-gray-300 border border-gray-600/50 shadow-[0_0_10px_rgba(0,0,0,0.5)] hover:bg-gray-800 hover:text-white hover:border-gray-500 hover:shadow-[0_0_15px_rgba(156,163,175,0.2)]',
    danger: 'bg-gradient-to-r from-red-900 to-red-950 text-red-100 border border-red-700/50 shadow-[0_0_15px_rgba(220,38,38,0.3)] hover:from-red-800 hover:to-red-900 hover:shadow-[0_0_20px_rgba(220,38,38,0.5)]',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
