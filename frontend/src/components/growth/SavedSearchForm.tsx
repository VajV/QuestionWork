"use client";

import { useState } from "react";
import { createSavedSearch, getApiErrorMessage, type SavedSearch, type SavedSearchCreate } from "@/lib/api";

interface Props {
  searchType: "talent" | "quest";
  filtersJson: Record<string, unknown>;
  onSaved?: (saved: SavedSearch) => void;
}

export default function SavedSearchForm({ searchType, filtersJson, onSaved }: Props) {
  const [name, setName] = useState("");
  const [alertEnabled, setAlertEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload: SavedSearchCreate = {
        name: name.trim() || undefined,
        search_type: searchType,
        filters_json: filtersJson,
        alert_enabled: alertEnabled,
      };
      const result = await createSavedSearch(payload);
      setSaved(true);
      onSaved?.(result);
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "Не удалось сохранить поиск");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  if (saved) {
    return (
      <p className="text-sm text-purple-400 font-medium">
        ✓ Поиск сохранён
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 text-sm">
      <input
        type="text"
        placeholder="Название поиска (необязательно)"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={200}
        className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
      />
      <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
        <input
          type="checkbox"
          checked={alertEnabled}
          onChange={(e) => setAlertEnabled(e.target.checked)}
          className="accent-purple-500"
        />
        Уведомлять о новых результатах
      </label>
      {error && <p className="text-red-400 text-xs">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="self-start bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded px-4 py-1.5 font-medium transition-colors"
      >
        {loading ? "Сохранение…" : "Сохранить поиск"}
      </button>
    </form>
  );
}
