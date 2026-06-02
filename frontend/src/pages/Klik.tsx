import React, { useEffect, useMemo, useState } from 'react';
import {
    Smartphone,
    RefreshCw,
    ShieldCheck,
    Clock,
    AlertCircle,
    Wallet,
    CheckCircle2,
    XCircle,
    Store,
} from 'lucide-react';
import api from '../api/axios';

interface Account {
    id: string;
    account_number: string;
    sort_code: string;
    iban: string;
    currency: string;
    balance: string;
    available_balance: string;
    account_type: string;
    status: string;
}

interface PendingPayment {
    transaction_id: string;
    amount: string;
    currency: string;
    merchant_name: string;
    expiry_time: string | null;
    status: string;
}

const Klik = () => {
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [pendingPayments, setPendingPayments] = useState<PendingPayment[]>([]);
    const [code, setCode] = useState('');
    const [timeLeft, setTimeLeft] = useState(0);
    const [loading, setLoading] = useState(false);
    const [pendingLoading, setPendingLoading] = useState(false);
    const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

    const currentAccount = useMemo(() => {
        return accounts.find(
            acc => acc.account_type === 'CURRENT' && acc.status === 'ACTIVE'
        );
    }, [accounts]);

    const fetchAccounts = async () => {
        try {
            const res = await api.get('/accounts/');
            setAccounts(res.data);
        } catch (err) {
            console.error('Failed to fetch accounts', err);
        }
    };

    const fetchPendingPayments = async () => {
        try {
            setPendingLoading(true);
            const res = await api.get('/klik/pending/');
            setPendingPayments(res.data);
        } catch (err) {
            console.error('Failed to fetch pending KLIK payments', err);
        } finally {
            setPendingLoading(false);
        }
    };

    useEffect(() => {
        fetchAccounts();
        fetchPendingPayments();

        const interval = setInterval(() => {
            fetchPendingPayments();
        }, 5000);

        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (timeLeft <= 0) {
            setCode('');
            return;
        }

        const interval = setInterval(() => {
            setTimeLeft(prev => prev - 1);
        }, 1000);

        return () => clearInterval(interval);
    }, [timeLeft]);

    const formatTime = (seconds: number) => {
        const min = Math.floor(seconds / 60);
        const sec = seconds % 60;
        return `${min}:${sec.toString().padStart(2, '0')}`;
    };

    const handleGenerateCode = async () => {
        if (!currentAccount) return;

        setLoading(true);

        try {
            const res = await api.post('/klik/generate-code/');
            setCode(res.data.code);
            setTimeLeft(res.data.expires_in ?? 120);
        } catch (err) {
            console.error('Failed to generate KLIK code', err);
        } finally {
            setLoading(false);
        }
    };

    const handleAcceptPayment = async (transactionId: string) => {
        setActionLoadingId(transactionId);

        try {
            await api.post(`/klik/pending/${transactionId}/accept/`);
            await fetchPendingPayments();
            await fetchAccounts();
        } catch (err) {
            console.error('Failed to accept KLIK payment', err);
        } finally {
            setActionLoadingId(null);
        }
    };

    const handleRejectPayment = async (transactionId: string) => {
        setActionLoadingId(transactionId);

        try {
            await api.post(`/klik/pending/${transactionId}/reject/`);
            await fetchPendingPayments();
        } catch (err) {
            console.error('Failed to reject KLIK payment', err);
        } finally {
            setActionLoadingId(null);
        }
    };

    return (
        <div className="h-full overflow-y-auto custom-scrollbar">
            <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

                <section>
                    <div className="flex items-center gap-4 mb-2">
                        <div className="w-14 h-14 rounded-3xl bg-[#00FF85]/10 border border-[#00FF85]/20 flex items-center justify-center">
                            <Smartphone className="text-[#00FF85]" size={28} />
                        </div>

                        <div>
                            <h1 className="text-3xl font-black text-[var(--text-primary)] tracking-tight">
                                KLIK
                            </h1>
                            <p className="text-[var(--text-muted)] text-sm">
                                Generate a one-time payment code and confirm KLIK payments.
                            </p>
                        </div>
                    </div>
                </section>

                {!currentAccount ? (
                    <div className="rounded-[2rem] border border-yellow-500/20 bg-yellow-500/10 p-6 flex items-start gap-4">
                        <AlertCircle className="text-yellow-400 shrink-0" size={24} />

                        <div>
                            <h2 className="text-lg font-bold text-[var(--text-primary)]">
                                KLIK is not available
                            </h2>
                            <p className="text-sm text-[var(--text-muted)] mt-1">
                                KLIK payments are available only for active current accounts.
                                Junior accounts cannot use this feature.
                            </p>
                        </div>
                    </div>
                ) : (
                    <>
                        <section className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-6">
                            <div className="rounded-[2rem] border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-xl">
                                <h2 className="text-lg font-bold text-[var(--text-primary)] mb-4">
                                    Your KLIK account
                                </h2>

                                <div className="rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border)] p-5">
                                    <div className="flex items-center gap-3 mb-5">
                                        <div className="w-12 h-12 rounded-2xl bg-[#00FF85]/10 flex items-center justify-center">
                                            <Wallet className="text-[#00FF85]" size={24} />
                                        </div>

                                        <div>
                                            <p className="text-sm text-[var(--text-muted)]">
                                                Current account
                                            </p>
                                            <p className="text-lg font-black text-[var(--text-primary)]">
                                                {currentAccount.sort_code} {currentAccount.account_number}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <div className="flex justify-between text-sm">
                                            <span className="text-[var(--text-muted)]">Balance</span>
                                            <span className="font-bold text-[var(--text-primary)]">
                                                £{currentAccount.available_balance}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <div className="mt-6 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border)] p-4">
                                    <div className="flex items-center gap-3">
                                        <ShieldCheck className="text-[#00FF85]" size={22} />

                                        <div>
                                            <p className="text-sm font-bold text-[var(--text-primary)]">
                                                Secure one-time code
                                            </p>
                                            <p className="text-xs text-[var(--text-muted)]">
                                                The code is valid for 2 minutes and can be used only once.
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-[2rem] border border-[#00FF85]/20 bg-[#00FF85]/5 p-8 shadow-xl text-center">
                                <p className="text-xs font-black uppercase tracking-[0.3em] text-[#00FF85] mb-4">
                                    Payment code
                                </p>

                                <div className="min-h-[110px] flex items-center justify-center">
                                    {code ? (
                                        <h2 className="text-6xl sm:text-7xl font-black tracking-widest text-[var(--text-primary)]">
                                            {code}
                                        </h2>
                                    ) : (
                                        <p className="text-[var(--text-muted)] text-sm max-w-sm">
                                            Click the button below to generate a KLIK code.
                                        </p>
                                    )}
                                </div>

                                {code && (
                                    <div className="mt-4 flex items-center justify-center gap-2 text-sm text-[var(--text-muted)]">
                                        <Clock size={18} />
                                        <span>Valid for:</span>
                                        <span className="font-bold text-[#00FF85]">
                                            {formatTime(timeLeft)}
                                        </span>
                                    </div>
                                )}

                                <button
                                    onClick={handleGenerateCode}
                                    disabled={loading}
                                    className="mt-8 w-full py-4 rounded-2xl bg-[#00FF85] hover:bg-[#00e074] text-black font-black transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
                                    {code ? 'Generate new code' : 'Generate KLIK code'}
                                </button>
                            </div>
                        </section>

                        <section className="rounded-[2rem] border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-xl">
                            <div className="flex items-center justify-between gap-4 mb-5">
                                <div>
                                    <h2 className="text-lg font-bold text-[var(--text-primary)]">
                                        Pending confirmations
                                    </h2>
                                    <p className="text-sm text-[var(--text-muted)] mt-1">
                                        Confirm or reject payments initiated with your KLIK code.
                                    </p>
                                </div>

                                <button
                                    onClick={fetchPendingPayments}
                                    disabled={pendingLoading}
                                    className="px-4 py-2 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border)] text-sm font-bold text-[var(--text-primary)] hover:border-[#00FF85] transition-all disabled:opacity-50"
                                >
                                    Refresh
                                </button>
                            </div>

                            {pendingPayments.length === 0 ? (
                                <div className="rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border)] p-5 text-center">
                                    <p className="text-sm text-[var(--text-muted)]">
                                        No pending KLIK payments.
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {pendingPayments.map(payment => (
                                        <div
                                            key={payment.transaction_id}
                                            className="rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border)] p-5"
                                        >
                                            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
                                                <div className="flex items-start gap-4">
                                                    <div className="w-12 h-12 rounded-2xl bg-[#00FF85]/10 flex items-center justify-center shrink-0">
                                                        <Store className="text-[#00FF85]" size={24} />
                                                    </div>

                                                    <div>
                                                        <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)] font-black">
                                                            Merchant
                                                        </p>
                                                        <h3 className="text-xl font-black text-[var(--text-primary)]">
                                                            {payment.merchant_name || 'Unknown merchant'}
                                                        </h3>

                                                        <p className="text-sm text-[var(--text-muted)] mt-2">
                                                            Transaction ID: {payment.transaction_id}
                                                        </p>

                                                        {payment.expiry_time && (
                                                            <p className="text-sm text-[var(--text-muted)] mt-1">
                                                                Expires at: {new Date(payment.expiry_time).toLocaleString()}
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="lg:text-right">
                                                    <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)] font-black">
                                                        Amount
                                                    </p>
                                                    <p className="text-3xl font-black text-[var(--text-primary)]">
                                                        {payment.currency} {payment.amount}
                                                    </p>

                                                    <div className="flex flex-col sm:flex-row gap-3 mt-4">
                                                        <button
                                                            onClick={() => handleAcceptPayment(payment.transaction_id)}
                                                            disabled={actionLoadingId === payment.transaction_id}
                                                            className="px-5 py-3 rounded-2xl bg-[#00FF85] hover:bg-[#00e074] text-black font-black transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                                        >
                                                            <CheckCircle2 size={20} />
                                                            Accept
                                                        </button>

                                                        <button
                                                            onClick={() => handleRejectPayment(payment.transaction_id)}
                                                            disabled={actionLoadingId === payment.transaction_id}
                                                            className="px-5 py-3 rounded-2xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 font-black transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                                        >
                                                            <XCircle size={20} />
                                                            Reject
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>
                    </>
                )}
            </div>
        </div>
    );
};

export default Klik;