"use client";

import { useEffect, useRef } from "react";

interface AudioVisualizerProps {
  analyser: AnalyserNode | null;
  isPlaying: boolean;
  /** accent colour used for bars — defaults to amber */
  color?: string;
}

/**
 * Full-width frequency-bar visualizer.
 * Reads from a Web Audio AnalyserNode every animation frame and draws
 * symmetric bars (top + bottom mirror) centred on the canvas midline.
 */
export default function AudioVisualizer({
  analyser,
  isPlaying,
  color = "#f59e0b",
}: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // ── resize helper ────────────────────────────────────────────────
    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // ── stop any existing loop ───────────────────────────────────────
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    if (!isPlaying || !analyser) {
      // Draw an idle flat line when not playing
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const midY = canvas.height / 2;
      ctx.strokeStyle = `${color}44`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, midY);
      ctx.lineTo(canvas.width, midY);
      ctx.stroke();
      ro.disconnect();
      return;
    }

    const bufferLength = analyser.frequencyBinCount; // 128 bins
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);

      analyser.getByteFrequencyData(dataArray);

      const W = canvas.width;
      const H = canvas.height;
      const midY = H / 2;

      ctx.clearRect(0, 0, W, H);

      // Background gradient — subtle dark
      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "rgba(0,0,0,0.0)");
      bg.addColorStop(1, "rgba(0,0,0,0.0)");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      const barCount = bufferLength;
      const barWidth = W / barCount;
      const halfH = midY * 0.85; // max bar reaches 85% of half-height

      for (let i = 0; i < barCount; i++) {
        const v = dataArray[i] / 255; // 0 → 1
        const barH = v * halfH;

        // Glow gradient per bar — accent colour with alpha falloff
        const x = i * barWidth;
        const grad = ctx.createLinearGradient(x, midY - barH, x, midY + barH);
        grad.addColorStop(0, `${color}00`);
        grad.addColorStop(0.3, `${color}99`);
        grad.addColorStop(0.5, `${color}ff`);
        grad.addColorStop(0.7, `${color}99`);
        grad.addColorStop(1, `${color}00`);

        ctx.fillStyle = grad;
        ctx.fillRect(
          x + 1,
          midY - barH,
          Math.max(barWidth - 2, 1),
          barH * 2, // symmetric: top + bottom
        );
      }

      // Centre line
      ctx.strokeStyle = `${color}30`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, midY);
      ctx.lineTo(W, midY);
      ctx.stroke();
    };

    draw();

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [analyser, isPlaying, color]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full block"
      aria-hidden="true"
    />
  );
}
