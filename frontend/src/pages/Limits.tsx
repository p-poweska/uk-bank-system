import React, { useEffect, useMemo, useState } from 'react';
import api from '../api/axios';

type ActiveTab = 'CARDS' | 'KLIK';
type LimitChannel = 'CARD' | 'BLIK' | 'BLIK_PHONE';

type DraftLimit = {
    per_transaction_limit: string;
    daily_limit: string;
};

const toMoneyInput = (value: unknown): string => {
    const parsed = Number(value ?? 0);
    return Number.isNaN(parsed) ? '0.00' : parsed.toFixed(2);
};

const Limits = () => {
    const [accounts, setAccounts] = useState<any[]>([]);
    const [selectedAccountId, setSelectedAccountId] = useState<string>('');
    const [activeTab, setActiveTab] = useState<ActiveTab>('CARDS');
    const [drafts, setDrafts] = useState<Record<string, DraftLimit>>({});
    const [savingKey, setSavingKey] = useState<string | null>(null);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const selectedAccount = useMemo(() => {
        return accounts.find((account) => account.id === selectedAccountId);
    }, [accounts, selectedAccountId]);

    const loadAccounts = async () => {
        const response = await api.get('/accounts/');
        const data = Array.isArray(response.data)
            ? response.data
            : response.data.accounts || [];

        setAccounts(data);

        if (!selectedAccountId && data.length > 0) {
            setSelectedAccountId(data[0].id);
        }

        const nextDrafts: Record<string, DraftLimit> = {};

        data.forEach((account: any) => {
            const blikLimit = account.limits?.BLIK;
            const blikPhoneLimit = account.limits?.BLIK_PHONE;

            nextDrafts[`BLIK:${account.id}`] = {
                per_transaction_limit: toMoneyInput(blikLimit?.per_transaction_limit),
                daily_limit: toMoneyInput(blikLimit?.daily_limit),
            };

            nextDrafts[`BLIK_PHONE:${account.id}`] = {
                per_transaction_limit: toMoneyInput(blikPhoneLimit?.per_transaction_limit),
                daily_limit: toMoneyInput(blikPhoneLimit?.daily_limit),
            };

            const cards = account.cards || [];

            cards.forEach((card: any) => {
                nextDrafts[`CARD:${card.id}`] = {
                    per_transaction_limit: toMoneyInput(card.limits?.per_transaction_limit),
                    daily_limit: toMoneyInput(card.limits?.daily_limit),
                };
            });
        });

        setDrafts(nextDrafts);
    };

    useEffect(() => {
        loadAccounts();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const updateDraft = (
        key: string,
        field: keyof DraftLimit,
        value: string,
    ) => {
        setDrafts((previous) => ({
            ...previous,
            [key]: {
                ...previous[key],
                [field]: value,
            },
        }));
    };

    const saveLimit = async (
        channel: LimitChannel,
        options: {
            accountId?: string;
            cardId?: string;
        },
    ) => {
        setError('');
        setSuccess('');

        const key = `${channel}:${options.cardId || options.accountId}`;
        const draft = drafts[key];

        if (!draft) {
            setError('Limit data was not loaded.');
            return;
        }

        const perTransaction = Number(draft.per_transaction_limit);
        const daily = Number(draft.daily_limit);

        if (Number.isNaN(perTransaction) || Number.isNaN(daily)) {
            setError('Limit value is invalid.');
            return;
        }

        if (perTransaction < 0 || daily < 0) {
            setError('Limits cannot be negative.');
            return;
        }

        if (perTransaction > daily) {
            setError('Per transaction limit cannot be higher than daily limit.');
            return;
        }

        setSavingKey(key);

        try {
            await api.patch('/accounts/limits/', {
                channel,
                account_id: options.accountId,
                card_id: options.cardId,
                per_transaction_limit: draft.per_transaction_limit,
                daily_limit: draft.daily_limit,
            });

            setSuccess('Limits updated successfully.');
            await loadAccounts();
        } catch (err: any) {
            setError(
                err.response?.data?.error ||
                err.response?.data?.detail ||
                'Could not update limits.',
            );
        } finally {
            setSavingKey(null);
        }
    };

    const selectedCards = selectedAccount?.cards || [];

    const LimitInput = ({
        label,
        value,
        onChange,
    }: {
        label: string;
        value: string;
        onChange: (value: string) => void;
    }) => (
        <div>
            <label className="block mb-2 text-[9px] sm:text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                {label}
            </label>

            <div className="flex h-11 items-center rounded-xl border border-[var(--border)] bg-[var(--bg-base)] px-4 focus-within:border-[#00FF85]/50 transition-colors">
                <span className="mr-2 font-black text-[var(--text-muted)]">£</span>
                <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    className="w-full bg-transparent outline-none font-mono text-sm sm:text-base text-[var(--text-primary)]"
                />
            </div>
        </div>
    );

    const SaveButton = ({
        onClick,
        loading,
    }: {
        onClick: () => void;
        loading: boolean;
    }) => (
        <button
            onClick={onClick}
            disabled={loading}
            className="mt-5 w-full h-11 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-5 text-[10px] font-bold uppercase tracking-widest text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all"
        >
            {loading ? 'Saving...' : 'Save changes'}
        </button>
    );

    return (
        <div className="flex-1 p-4 sm:p-5 md:p-6 text-[var(--text-primary)] flex flex-col lg:flex-row gap-5 md:gap-6 w-full">
            
            {/* LEFT COLUMN: account list */}
            <div className="flex w-full lg:w-64 shrink-0 flex-col gap-2">
                <h2 className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1.5 px-1">My Accounts</h2>
                <div className="flex flex-row lg:flex-col gap-2.5 overflow-x-auto no-scrollbar pb-2 lg:pb-0">
                    {accounts.map((acc) => {
                        const isJunior = acc.account_type === 'JUNIOR';
                        const isSelected = selectedAccountId === acc.id;
                        return (
                            <button
                                key={acc.id}
                                onClick={() => setSelectedAccountId(acc.id)}
                                className={`flex items-center gap-3 shrink-0 lg:shrink w-[220px] lg:w-full p-2.5 rounded-xl transition-all border
                                ${isSelected
                                    ? (isJunior ? 'bg-purple-500/10 border-purple-500/50' : 'bg-emerald-500/10 border-emerald-500/30')
                                    : 'bg-[var(--bg-surface)] lg:bg-transparent hover:bg-[var(--bg-elevated)] border-[var(--border)] lg:border-transparent'}`}
                            >
                                <div className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center ${isSelected ? (isJunior ? 'bg-purple-500 text-white' : 'bg-[#00FF85] text-black') : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'}`}>
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        {isJunior
                                            ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                            : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />}
                                    </svg>
                                </div>
                                <div className="text-left flex-1 overflow-hidden flex items-center justify-between gap-2">
                                    <span className="text-sm font-bold truncate">
                                        {isJunior ? acc.owner_first_name || 'Junior' : 'Current'}
                                    </span>
                                    <span className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded shrink-0 border ${
                                        isJunior
                                            ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                                            : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                    }`}>
                                        {isJunior ? 'Junior' : 'Current'}
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* RIGHT COLUMN: details */}
            <div className="flex-1 flex flex-col h-full pr-2 pb-6 w-full">
                <div className="flex flex-col gap-4 animate-fadeIn max-w-3xl w-full mx-auto">
                    
                    {/* Header */}
                    <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-3xl p-5 sm:p-6 shadow-lg">
                        <h2 className="text-[10px] sm:text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1.5">
                            Payment Controls
                        </h2>
                        <h1 className="text-4xl sm:text-5xl font-black tracking-tighter text-[var(--text-primary)]">
                            Limits
                        </h1>
                        <p className="mt-2 text-sm text-[var(--text-muted)]">
                            Manage daily and per transaction limits for cards and KLIK payments.
                        </p>
                    </div>

                    {error && (
                        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-bold text-red-400">
                            {error}
                        </div>
                    )}

                    {success && (
                        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-bold text-emerald-400">
                            {success}
                        </div>
                    )}

                    {selectedAccount ? (
                        <>
                            {/* Tabs & Title */}
                            <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-3xl p-4 sm:p-5 shadow-lg">
                                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                    <div>
                                        <h2 className="text-lg font-black text-[var(--text-secondary)]">
                                            {activeTab === 'CARDS' ? 'Card Limits' : 'KLIK Limits'}
                                        </h2>
                                        <p className="text-xs text-[var(--text-muted)] mt-1">
                                            {activeTab === 'CARDS'
                                                ? 'Limits are configured separately for each card.'
                                                : 'Separate limits for code payments and phone transfers.'}
                                        </p>
                                    </div>

                                    <div className="flex rounded-2xl border border-[var(--border)] bg-[var(--bg-base)] p-1 w-fit shrink-0">
                                        <button
                                            onClick={() => setActiveTab('CARDS')}
                                            className={`rounded-xl px-5 py-2 text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'CARDS'
                                                    ? 'bg-[#00FF85] text-black shadow-sm'
                                                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                                                }`}
                                        >
                                            Cards
                                        </button>
                                        <button
                                            onClick={() => setActiveTab('KLIK')}
                                            className={`rounded-xl px-5 py-2 text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'KLIK'
                                                    ? 'bg-[#00FF85] text-black shadow-sm'
                                                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                                                }`}
                                        >
                                            KLIK
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Forms Cards */}
                            {activeTab === 'CARDS' && (
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {selectedCards.length === 0 && (
                                        <div className="col-span-1 sm:col-span-2 rounded-3xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 text-center text-sm font-bold text-[var(--text-muted)] shadow-lg">
                                            No cards available for this account.
                                        </div>
                                    )}

                                    {selectedCards.map((card: any) => {
                                        const key = `CARD:${card.id}`;
                                        const draft = drafts[key] || {
                                            per_transaction_limit: '0.00',
                                            daily_limit: '0.00',
                                        };

                                        return (
                                            <div
                                                key={card.id}
                                                className="rounded-3xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-lg flex flex-col"
                                            >
                                                <div className="mb-5 flex items-start justify-between gap-3 border-b border-[var(--border)]/50 pb-4">
                                                    <div>
                                                        <p className="text-sm font-bold text-[var(--text-secondary)]">
                                                            {card.card_type} Card
                                                        </p>
                                                        <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)] tracking-widest">
                                                            {card.masked_number}
                                                        </p>
                                                    </div>
                                                    <span className="rounded px-1.5 py-0.5 border border-emerald-500/20 bg-emerald-500/10 text-[8px] font-black uppercase tracking-widest text-emerald-400">
                                                        {card.status}
                                                    </span>
                                                </div>

                                                <div className="flex flex-col gap-4 flex-1">
                                                    <LimitInput
                                                        label="Per transaction"
                                                        value={draft.per_transaction_limit}
                                                        onChange={(value) =>
                                                            updateDraft(key, 'per_transaction_limit', value)
                                                        }
                                                    />
                                                    <LimitInput
                                                        label="Daily limit"
                                                        value={draft.daily_limit}
                                                        onChange={(value) =>
                                                            updateDraft(key, 'daily_limit', value)
                                                        }
                                                    />
                                                </div>

                                                <SaveButton
                                                    loading={savingKey === key}
                                                    onClick={() =>
                                                        saveLimit('CARD', {
                                                            cardId: card.id,
                                                        })
                                                    }
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            {activeTab === 'KLIK' && selectedAccount && (
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {[
                                        {
                                            channel: 'BLIK' as const,
                                            title: 'KLIK Code Payments',
                                            description: 'Used for one-time payment codes.',
                                        },
                                        {
                                            channel: 'BLIK_PHONE' as const,
                                            title: 'KLIK Phone Transfers',
                                            description: 'Used for transfers by phone number.',
                                        },
                                    ].map((item) => {
                                        const key = `${item.channel}:${selectedAccount.id}`;
                                        const draft = drafts[key] || {
                                            per_transaction_limit: '0.00',
                                            daily_limit: '0.00',
                                        };

                                        return (
                                            <div
                                                key={item.channel}
                                                className="rounded-3xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-lg flex flex-col"
                                            >
                                                <div className="mb-5 flex items-start justify-between gap-3 border-b border-[var(--border)]/50 pb-4">
                                                    <div>
                                                        <p className="text-sm font-bold text-[var(--text-secondary)]">
                                                            {item.title}
                                                        </p>
                                                        <p className="mt-1 text-[10px] font-semibold text-[var(--text-muted)]">
                                                            {item.description}
                                                        </p>
                                                    </div>
                                                    <span className="rounded px-1.5 py-0.5 border border-emerald-500/20 bg-emerald-500/10 text-[8px] font-black uppercase tracking-widest text-emerald-400">
                                                        KLIK
                                                    </span>
                                                </div>

                                                <div className="flex flex-col gap-4 flex-1">
                                                    <LimitInput
                                                        label="Per transaction"
                                                        value={draft.per_transaction_limit}
                                                        onChange={(value) =>
                                                            updateDraft(key, 'per_transaction_limit', value)
                                                        }
                                                    />
                                                    <LimitInput
                                                        label="Daily limit"
                                                        value={draft.daily_limit}
                                                        onChange={(value) =>
                                                            updateDraft(key, 'daily_limit', value)
                                                        }
                                                    />
                                                </div>

                                                <SaveButton
                                                    loading={savingKey === key}
                                                    onClick={() =>
                                                        saveLimit(item.channel, {
                                                            accountId: selectedAccount.id,
                                                        })
                                                    }
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="text-center p-20 text-sm font-bold" style={{ color: 'var(--text-muted)' }}>
                            No account selected.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Limits;