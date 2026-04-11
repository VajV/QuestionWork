/**
 * WalletPanel — wallet section on the user profile page.
 *
 * Shows:
 * - Current balance (with currency switcher)
 * - Total earned
 * - Expandable transaction history (last 10)
 *
 * Only visible to the profile owner.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "@/lib/motion";
import {
  Wallet,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  ArrowUpRight,
  ArrowDownLeft,
  History,
  ArrowRightLeft,
  CheckCircle,
  XCircle,
  Download,
} from "lucide-react";
import {
  downloadWalletReceipt,
  downloadWalletStatement,
  getWalletBalance,
  getWalletTransactions,
  requestWithdrawal,
  type WalletTransaction,
  type WalletStatementFormat,
  getApiErrorMessage,
  getApiErrorStatus,
} from "@/lib/api";
import {
  type CurrencyCode,
  CURRENCY_LIST,
  CURRENCIES,
  getPreferredCurrency,
  setPreferredCurrency,
  convertCurrency,
  formatBalance,
} from "@/lib/currency";
import { safeParseMoney } from "@/lib/money";

export default function WalletPanel() {
  const [balanceBase, setBalanceBase] = useState(0);
  const [balanceBaseCurrency, setBalanceBaseCurrency] = useState<CurrencyCode>("RUB");
  const [totalEarned, setTotalEarned] = useState(0);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [currency, setCurrency] = useState<CurrencyCode>("RUB");
  const [showHistory, setShowHistory] = useState(false);
  const [txLoaded, setTxLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [receiptLoadingId, setReceiptLoadingId] = useState<string | null>(null);
  const [statementFrom, setStatementFrom] = useState("");
  const [statementTo, setStatementTo] = useState("");
  const [statementFormat, setStatementFormat] = useState<WalletStatementFormat>("pdf");
  const [statementLoading, setStatementLoading] = useState(false);

  // Withdrawal form state
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [withdrawCurrency, setWithdrawCurrency] = useState<CurrencyCode>("RUB");
  const [withdrawLoading, setWithdrawLoading] = useState(false);
  const [withdrawResult, setWithdrawResult] = useState<{
    transaction_id: string;
    amount: number;
    currency: string;
    status: string;
    new_balance: number;
  } | null>(null);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  useEffect(() => {
    setCurrency(getPreferredCurrency());
  }, []);

  const fetchWallet = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWalletBalance();
      // P2-10: use the first available balance currency, not hardcoded RUB
      const primary = data.balances[0];
      setBalanceBase(primary?.balance ?? 0);
      setBalanceBaseCurrency((primary?.currency as CurrencyCode) ?? "RUB");
      setTotalEarned(data.total_earned ?? 0);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить кошелёк"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchWallet().then(() => {
      if (cancelled) return;
    });
    return () => { cancelled = true; };
  }, [fetchWallet]);

  // Fetch transactions on demand; after first load, button simply toggles visibility
  const loadTransactions = useCallback(async () => {
    if (txLoaded) {
      setTxError(null);
      setShowHistory((prev) => !prev);
      return;
    }
    setTxLoading(true);
    setTxError(null);
    try {
      const data = await getWalletTransactions(10, 0);
      setTransactions(data.transactions);
      setTxLoaded(true);
      setShowHistory(true);
    } catch (err: unknown) {
      setTxError(getApiErrorMessage(err, "Не удалось загрузить историю транзакций"));
    } finally {
      setTxLoading(false);
    }
  }, [txLoaded]);

  const handleCurrencyChange = (code: CurrencyCode) => {
    setCurrency(code);
    setPreferredCurrency(code);
  };

  const triggerBrowserDownload = useCallback((blob: Blob, fallbackName: string, filename?: string | null) => {
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename || fallbackName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }, []);

  const handleReceiptDownload = useCallback(async (transactionId: string) => {
    setReceiptLoadingId(transactionId);
    setDocumentError(null);
    try {
      const file = await downloadWalletReceipt(transactionId);
      triggerBrowserDownload(file.blob, `receipt-${transactionId}.pdf`, file.filename);
    } catch (err: unknown) {
      setDocumentError(getApiErrorMessage(err, "Не удалось скачать чек"));
    } finally {
      setReceiptLoadingId((current) => (current === transactionId ? null : current));
    }
  }, [triggerBrowserDownload]);

  const handleStatementDownload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!statementFrom || !statementTo) {
      setDocumentError("Укажите период выписки");
      return;
    }
    if (statementFrom > statementTo) {
      setDocumentError("Дата начала не может быть позже даты окончания");
      return;
    }

    setStatementLoading(true);
    setDocumentError(null);
    try {
      const file = await downloadWalletStatement(statementFrom, statementTo, statementFormat);
      const fallbackName = `wallet-statement-${statementFrom}-${statementTo}.${statementFormat}`;
      triggerBrowserDownload(file.blob, fallbackName, file.filename);
    } catch (err: unknown) {
      setDocumentError(getApiErrorMessage(err, "Не удалось скачать выписку"));
    } finally {
      setStatementLoading(false);
    }
  };

  const handleWithdraw = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = safeParseMoney(withdrawAmount);
    if (amt === null || amt <= 0) {
      setWithdrawError("Введите корректную сумму");
      return;
    }
    // Convert balance to withdrawal currency for proper comparison
    const balanceInWithdrawCurrency = convertCurrency(balanceBase, balanceBaseCurrency, withdrawCurrency);
    if (amt > balanceInWithdrawCurrency) {
      setWithdrawError("Сумма превышает баланс");
      return;
    }
    setWithdrawLoading(true);
    setWithdrawError(null);
    setWithdrawResult(null);
    try {
      const result = await requestWithdrawal(amt, withdrawCurrency);
      setWithdrawResult(result);
      setWithdrawAmount("");
      // Refresh balance
      const updated = await getWalletBalance();
      const updatedPrimary = updated.balances[0];
      setBalanceBase(updatedPrimary?.balance ?? 0);
      setBalanceBaseCurrency((updatedPrimary?.currency as CurrencyCode) ?? "RUB");
    } catch (err: unknown) {
      const status = getApiErrorStatus(err);
      if (status === 402) {
        setWithdrawError("Недостаточно средств на балансе");
      } else if (status === 400) {
        setWithdrawError("Сумма ниже минимальной или некорректна");
      } else {
        setWithdrawError(getApiErrorMessage(err, "Ошибка запроса вывода"));
      }
    } finally {
      setWithdrawLoading(false);
    }
  };

  const displayBalance = convertCurrency(balanceBase, balanceBaseCurrency, currency);
  const rawEarned = convertCurrency(totalEarned, balanceBaseCurrency, currency);
  const displayEarned = Number.isFinite(rawEarned) ? rawEarned : 0;

  const txTypeLabels: Record<string, { label: string; color: string; icon: typeof ArrowUpRight }> = {
    credit: { label: "Зачисление", color: "text-green-400", icon: ArrowDownLeft },
    income: { label: "Доход", color: "text-green-400", icon: ArrowDownLeft },
    commission: { label: "Комиссия платформы", color: "text-green-400", icon: ArrowDownLeft },
    quest_payment: { label: "Оплата квеста", color: "text-green-400", icon: ArrowDownLeft },
    urgent_bonus: { label: "Срочный бонус", color: "text-green-400", icon: ArrowDownLeft },
    debit: { label: "Списание", color: "text-red-400", icon: ArrowUpRight },
    withdrawal: { label: "Вывод", color: "text-orange-400", icon: ArrowUpRight },
    platform_fee: { label: "Комиссия", color: "text-gray-400", icon: ArrowUpRight },
  };

  const isPositiveTransaction = (type: string) => (
    type === "credit" ||
    type === "income" ||
    type === "commission" ||
    type === "quest_payment" ||
    type === "urgent_bonus"
  );

  if (loading) {
    return (
      <div className="rpg-card p-6 mt-6">
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-gray-700/50 rounded w-32" />
          <div className="h-10 bg-gray-700/50 rounded w-48" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rpg-card p-6 mt-6 !border-red-500/30">
        <p className="text-red-400 text-sm">{error}</p>
        <button type="button" onClick={fetchWallet} className="text-xs text-amber-500 hover:underline mt-1">
          Повторить
        </button>
      </div>
    );
  }

  return (
    <div className="rpg-card p-6 mt-6 relative overflow-hidden">
      {/* Decorative glow */}
      <div className="absolute top-0 right-0 w-40 h-40 bg-amber-600 rounded-full blur-[80px] opacity-10 pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-4 border-b border-amber-900/30 pb-2">
        <h3 className="text-xl font-cinzel text-amber-500 flex items-center gap-2">
          <Wallet className="text-amber-500" size={24} aria-hidden="true" />
          Кошелёк
        </h3>

        {/* Currency switcher */}
        <div className="flex items-center gap-1 bg-gray-900/60 rounded-lg p-0.5 border border-gray-800/50">
          {CURRENCY_LIST.map((code) => (
            <button
              type="button"
              key={code}
              onClick={() => handleCurrencyChange(code)}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                currency === code
                  ? "bg-amber-900/60 text-amber-300 border border-amber-700/50"
                  : "text-gray-500 hover:text-gray-300 border border-transparent"
              }`}
              aria-label={`Показать в ${CURRENCIES[code].label}`}
            >
              {CURRENCIES[code].symbol}
            </button>
          ))}
        </div>
      </div>

      {/* Balance cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative z-10">
        {/* Current balance */}
        <div className="bg-gradient-to-br from-gray-900 to-gray-950 rounded-lg p-4 border border-amber-900/20">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1 font-mono">
            Текущий баланс
          </div>
          <div className="text-2xl font-bold text-amber-300 font-mono">
            {formatBalance(displayBalance, currency)}
          </div>
        </div>

        {/* Total earned */}
        <div className="bg-gradient-to-br from-gray-900 to-gray-950 rounded-lg p-4 border border-green-900/20">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1 font-mono flex items-center gap-1">
            <TrendingUp size={12} className="text-green-500" />
            Всего заработано
          </div>
          <div className="text-2xl font-bold text-green-400 font-mono">
            {formatBalance(displayEarned, currency)}
          </div>
        </div>
      </div>

      <form
        onSubmit={handleStatementDownload}
        className="mt-4 rounded-lg border border-gray-800/40 bg-gray-950/40 p-4 space-y-3"
      >
        <div className="flex items-center gap-2 text-sm text-amber-400">
          <Download size={14} />
          Экспорт документов
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_auto_auto]">
          <label className="text-xs text-gray-400">
            <span className="mb-1 block">С</span>
            <input
              type="date"
              value={statementFrom}
              onChange={(e) => setStatementFrom(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800/60 px-3 py-2 text-sm text-white focus:border-amber-700/60 focus:outline-none"
              disabled={statementLoading}
            />
          </label>
          <label className="text-xs text-gray-400">
            <span className="mb-1 block">По</span>
            <input
              type="date"
              value={statementTo}
              onChange={(e) => setStatementTo(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800/60 px-3 py-2 text-sm text-white focus:border-amber-700/60 focus:outline-none"
              disabled={statementLoading}
            />
          </label>
          <label className="text-xs text-gray-400">
            <span className="mb-1 block">Формат</span>
            <select
              value={statementFormat}
              onChange={(e) => setStatementFormat(e.target.value as WalletStatementFormat)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800/60 px-3 py-2 text-sm text-white focus:border-amber-700/60 focus:outline-none"
              disabled={statementLoading}
            >
              <option value="pdf">PDF</option>
              <option value="csv">CSV</option>
            </select>
          </label>
          <button
            type="submit"
            disabled={statementLoading}
            className="rounded-lg border border-amber-700/40 bg-amber-900/30 px-4 py-2 text-sm text-amber-300 transition hover:bg-amber-800/40 disabled:cursor-not-allowed disabled:opacity-50 sm:self-end"
          >
            {statementLoading ? "Генерация..." : "Скачать выписку"}
          </button>
        </div>
        {documentError && (
          <div className="rounded-md border border-red-500/20 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {documentError}
          </div>
        )}
      </form>

      {/* Withdrawal section */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => {
            setShowWithdraw((v) => !v);
            setWithdrawError(null);
            setWithdrawResult(null);
          }}
          className="w-full flex items-center justify-center gap-2 py-2 text-sm text-amber-400/80 hover:text-amber-300 transition-colors border border-amber-900/30 hover:border-amber-700/50 rounded-lg"
        >
          <ArrowRightLeft size={14} />
          {showWithdraw ? "Скрыть вывод средств" : "Вывести средства"}
          {showWithdraw ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        <AnimatePresence>
          {showWithdraw && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <form
                onSubmit={handleWithdraw}
                className="mt-3 p-4 rounded-lg bg-gray-900/50 border border-amber-900/20 space-y-3"
              >
                <p className="text-xs text-gray-500 font-mono">Заявка на вывод средств (обработка до 3 рабочих дней)</p>

                <div className="flex gap-2">
                  <div className="flex-1">
                    <label htmlFor="wallet-withdraw-amount" className="mb-2 block text-xs text-gray-400">
                      Сумма вывода
                    </label>
                    <input
                    id="wallet-withdraw-amount"
                    type="number"
                    min="1"
                    step="0.01"
                    placeholder="Сумма"
                    value={withdrawAmount}
                    onChange={(e) => setWithdrawAmount(e.target.value)}
                    className="flex-1 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-amber-700/60 focus:outline-none transition font-mono"
                    disabled={withdrawLoading}
                  />
                  </div>
                  <div>
                    <label htmlFor="wallet-withdraw-currency" className="mb-2 block text-xs text-gray-400">
                      Валюта
                    </label>
                    <select
                    id="wallet-withdraw-currency"
                    value={withdrawCurrency}
                    onChange={(e) => setWithdrawCurrency(e.target.value as CurrencyCode)}
                    className="bg-gray-800/60 border border-gray-700 rounded-lg px-2 py-2 text-sm text-gray-300 focus:border-amber-700/60 focus:outline-none transition font-mono"
                    disabled={withdrawLoading}
                  >
                    {CURRENCY_LIST.map((code) => (
                      <option key={code} value={code}>{CURRENCIES[code].symbol} {code}</option>
                    ))}
                  </select>
                  </div>
                </div>

                {withdrawError && (
                  <div className="flex items-center gap-2 text-red-400 text-xs">
                    <XCircle size={12} /> {withdrawError}
                  </div>
                )}

                {withdrawResult && (
                  <div className="flex items-start gap-2 text-green-400 text-xs bg-green-900/10 border border-green-900/30 rounded-lg p-3">
                    <CheckCircle size={12} className="mt-0.5 shrink-0" />
                    <div>
                      <p className="font-medium">Заявка #{withdrawResult.transaction_id.slice(0, 8)} принята</p>
                      <p className="text-gray-400 mt-0.5">
                        Сумма: {withdrawResult.amount} {withdrawResult.currency} · Статус: {withdrawResult.status}
                      </p>
                      <p className="text-gray-400">
                        Остаток: {formatBalance(convertCurrency(withdrawResult.new_balance, withdrawResult.currency as CurrencyCode, currency), currency)}
                      </p>
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={withdrawLoading || !withdrawAmount}
                  className="w-full py-2 px-4 rounded-lg bg-amber-900/40 hover:bg-amber-800/50 border border-amber-700/40 hover:border-amber-600/60 text-amber-300 text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {withdrawLoading ? "Отправка..." : "Подать заявку"}
                </button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Transaction history toggle */}
      <button
        type="button"
        onClick={loadTransactions}
        disabled={txLoading}
        className="mt-4 w-full flex items-center justify-center gap-2 py-2 text-sm text-gray-400 hover:text-amber-400 transition-colors border border-gray-800/40 hover:border-amber-900/40 rounded-lg"
      >
        <History size={14} />
        {txLoading ? "Загрузка..." : showHistory ? "Скрыть историю" : "История транзакций"}
        {!txLoading && (showHistory ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
      </button>

      {/* Transaction list */}
      <AnimatePresence>
        {showHistory && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-1.5">
              {txError && (
                <div className="rounded-md border border-red-500/20 bg-red-950/20 px-3 py-2 text-xs text-red-300">
                  <div>{txError}</div>
                  <button
                    type="button"
                    onClick={loadTransactions}
                    className="mt-2 text-amber-400 hover:underline"
                  >
                    Повторить
                  </button>
                </div>
              )}

              {transactions.map((tx) => {
                const meta = txTypeLabels[tx.type] ?? {
                  label: tx.type,
                  color: "text-gray-400",
                  icon: ArrowUpRight,
                };
                const Icon = meta.icon;
                const txAmount = convertCurrency(tx.amount, tx.currency as CurrencyCode, currency);

                return (
                  <div
                    key={tx.id}
                    className="flex items-center justify-between gap-3 py-2 px-3 rounded-md bg-gray-900/40 border border-gray-800/30"
                  >
                    <div className="flex items-center gap-2">
                      <Icon size={14} className={meta.color} />
                      <div>
                        <span className="text-sm text-gray-300">{meta.label}</span>
                        <span className="text-[10px] text-gray-600 ml-2 font-mono">
                          {new Date(tx.created_at).toLocaleDateString("ru-RU", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                            timeZone: "UTC",
                          })}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`font-mono text-sm ${meta.color}`}>
                        {isPositiveTransaction(tx.type) ? "+" : "−"}
                        {formatBalance(txAmount, currency)}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleReceiptDownload(tx.id)}
                        disabled={receiptLoadingId === tx.id}
                        className="inline-flex items-center gap-1 rounded-md border border-gray-700/60 px-2 py-1 text-xs text-gray-300 transition hover:border-amber-700/50 hover:text-amber-300 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Download size={12} />
                        {receiptLoadingId === tx.id ? "..." : "Чек"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {transactions.length === 0 && (
              <p className="text-center text-gray-600 text-sm mt-3">Транзакций пока нет</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
