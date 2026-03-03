"use client";

/**
 * ErrorBoundary — catches unhandled render errors and shows a fallback
 * instead of crashing the entire app to a white screen.
 */

import React, { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional custom fallback UI. */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary] Uncaught error:", error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center p-8">
          <div className="rpg-card p-8 max-w-md w-full text-center">
            <span className="text-5xl mb-4 block">💀</span>
            <h2 className="text-2xl font-cinzel font-bold text-red-400 mb-3">
              Критическая ошибка
            </h2>
            <p className="text-gray-400 mb-2 text-sm">
              Произошла непредвиденная ошибка интерфейса.
            </p>
            {this.state.error && (
              <pre className="text-xs text-gray-500 bg-black/40 rounded p-3 mb-4 overflow-auto max-h-32 text-left">
                {this.state.error.message}
              </pre>
            )}
            <div className="flex gap-3 justify-center mt-4">
              <button
                onClick={this.handleRetry}
                className="px-6 py-2 rounded bg-amber-900/50 text-amber-400 border border-amber-700/50 font-cinzel text-sm hover:bg-amber-900/70 transition-colors"
              >
                🔄 Повторить
              </button>
              <button
                onClick={() => (window.location.href = "/")}
                className="px-6 py-2 rounded bg-gray-800/50 text-gray-300 border border-gray-700/50 font-cinzel text-sm hover:bg-gray-800/70 transition-colors"
              >
                🏠 На главную
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
