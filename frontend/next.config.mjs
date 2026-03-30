import withBundleAnalyzer from "@next/bundle-analyzer";

const analyzeBundles = withBundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const apiOrigin = new URL(
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001",
).origin;
const isDev = process.env.NODE_ENV !== "production";
const distDir = isDev ? ".next-dev" : ".next";
const devLoopbackOrigins = ["http://localhost:8001", "http://127.0.0.1:8001"];

// P0-08 FIX: unsafe-inline only in dev (Next.js HMR requires it);
// production uses strict self-only script-src.
const scriptSrc = isDev
  ? ["'self'", "'unsafe-inline'", "'unsafe-eval'"]
  : ["'self'"];
const connectSrc = ["'self'", apiOrigin];

if (isDev) {
  connectSrc.push(...devLoopbackOrigins, "ws:", "wss:");
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir,
  output: "standalone",
  compress: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              `script-src ${scriptSrc.join(" ")}`,
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: http://127.0.0.1:8001",
              "font-src 'self' data:",
              `connect-src ${connectSrc.join(" ")}`,
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "object-src 'none'",
              ...(isDev ? [] : ["upgrade-insecure-requests"]),
            ].join("; "),
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains",
          },
        ],
      },
    ];
  },
};

export default analyzeBundles(nextConfig);
