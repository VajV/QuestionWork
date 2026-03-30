"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { adminGetFunnelKPIs, getApiErrorMessage, type FunnelKPIs } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";

function pct(numerator: number, denominator: number): string {
  if (!denominator) return "—";
  return `${((numerator / denominator) * 100).toFixed(1)}%`;
}

interface FunnelRow {
  label: string;
  value: number;
  conversionLabel?: string;
  conversionValue?: string;
}

export default function AdminGrowthPage() {
  const [kpis, setKpis] = useState<FunnelKPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminGetFunnelKPIs()
      .then(setKpis)
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  const rows: FunnelRow[] = kpis
    ? [
        { label: "Landing views (tracked)", value: kpis.landing_views },
        {
          label: "Register started",
          value: kpis.register_started,
          conversionLabel: "Landing → Register",
          conversionValue: pct(kpis.register_started, kpis.landing_views),
        },
        {
          label: "Clients registered",
          value: kpis.clients_registered,
        },
        {
          label: "Clients with quests",
          value: kpis.clients_with_quests,
          conversionLabel: "Registered → Quest",
          conversionValue: pct(kpis.clients_with_quests, kpis.clients_registered),
        },
        { label: "Quests created", value: kpis.quests_created },
        { label: "Applications submitted", value: kpis.applications_submitted },
        {
          label: "Hires (assigned/in-progress)",
          value: kpis.hires,
          conversionLabel: "Quest → Hire",
          conversionValue: pct(kpis.hires, kpis.quests_created),
        },
        {
          label: "Confirmed completions",
          value: kpis.confirmed_completions,
          conversionLabel: "Hire → Completion",
          conversionValue: pct(kpis.confirmed_completions, kpis.hires),
        },
        {
          label: "Clients with repeat hire",
          value: kpis.clients_with_repeat_hire,
          conversionLabel: "Completion → Repeat",
          conversionValue: pct(kpis.clients_with_repeat_hire, kpis.confirmed_completions),
        },
      ]
    : [];

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin/dashboard" className="text-gray-400 hover:text-white text-sm">
            ← Панель администратора
          </Link>
        </div>

        <h1 className="text-2xl font-cinzel font-bold text-amber-400 mb-6 uppercase tracking-wider">
          📊 Growth Funnel KPIs
        </h1>

        {error && (
          <Card className="p-4 border-red-500/40 text-red-400 text-sm mb-4">{error}</Card>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && kpis && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Card className="overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700/60">
                    <th className="text-left py-3 px-4 text-gray-400 font-medium">Funnel step</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Count</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Conversion</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr
                      key={row.label}
                      className={`border-b border-gray-800/40 ${i % 2 === 0 ? "bg-gray-900/20" : ""}`}
                    >
                      <td className="py-3 px-4 text-gray-200">{row.label}</td>
                      <td className="py-3 px-4 text-right text-white font-semibold tabular-nums">
                        {row.value.toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-right text-purple-300 tabular-nums">
                        {row.conversionLabel && row.conversionValue ? (
                          <span title={row.conversionLabel}>{row.conversionValue}</span>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <p className="text-xs text-gray-500 mt-3">
              Counts are all-time totals. Analytics events are tracked from{" "}
              <code className="bg-gray-800 px-1 rounded">landing_view</code> onwards.
              Historical data before instrumentation will show 0.
            </p>
          </motion.div>
        )}
      </div>
    </main>
  );
}
