import React, { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import api from '../api/axios';
import CardDetailsModal from '../components/CardDetailsModal';
import CardManager from '../components/CardManager';
import TopUpModal from '../components/TopUpModal';
import ConfirmActionModal from '../components/ConfirmActionModal';

interface ContextType {
    firstName: string;
}

const Cards = () => {
    const context = useOutletContext<ContextType>();
    const firstName = context?.firstName || '';

    const [accounts, setAccounts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedAccount, setSelectedAccount] = useState<any>(null);

    const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
    const [isTopUpModalOpen, setIsTopUpModalOpen] = useState(false);
    const [isRemoveModalOpen, setIsRemoveModalOpen] = useState(false);

    const [activeTab, setActiveTab] = useState<
        'VIRTUAL' | 'PHYSICAL' | 'PREPAID'
    >('VIRTUAL');

    const [activeCardId, setActiveCardId] = useState<string | null>(
        null,
    );

    const [txLimit, setTxLimit] = useState('');
    const [dailyLimit, setDailyLimit] = useState('');
    const [blikTxLimit, setBlikTxLimit] = useState('');
    const [blikDailyLimit, setBlikDailyLimit] = useState('');
    const [isSavingLimits, setIsSavingLimits] = useState(false);

    const [isCardActionPending, setIsCardActionPending] =
        useState(false);

    const refreshData = useCallback(async () => {
        try {
            const response = await api.get('/accounts/');
            const fetchedAccounts = response.data;

            setAccounts(fetchedAccounts);

            setSelectedAccount((currentAccount: any) => {
                if (!currentAccount) {
                    return fetchedAccounts[0] || null;
                }

                return (
                    fetchedAccounts.find(
                        (account: any) =>
                            account.id === currentAccount.id,
                    ) ||
                    fetchedAccounts[0] ||
                    null
                );
            });
        } catch (error) {
            console.error('Refresh error:', error);
        }
    }, []);

    const syncAllCardStatuses = useCallback(async () => {
        try {
            await api.post('/cards/sync-all/');
            await refreshData();
        } catch (error) {
            console.error(
                'Automatic card synchronization failed:',
                error,
            );
        }
    }, [refreshData]);

    useEffect(() => {
        const init = async () => {
            try {
                const response = await api.get('/accounts/');

                setAccounts(response.data);

                if (response.data.length > 0) {
                    setSelectedAccount(response.data[0]);
                }
            } catch (error) {
                console.error('Load error:', error);
            } finally {
                setLoading(false);
            }
        };

        init();
    }, []);

    useEffect(() => {
        syncAllCardStatuses();

        const intervalId = window.setInterval(
            syncAllCardStatuses,
            30000,
        );

        return () => {
            window.clearInterval(intervalId);
        };
    }, [syncAllCardStatuses]);

    useEffect(() => {
        if (!selectedAccount) {
            return;
        }

        setTxLimit(
            selectedAccount.limits?.CARD?.per_transaction_limit ||
            '0.00',
        );

        setDailyLimit(
            selectedAccount.limits?.CARD?.daily_limit ||
            '0.00',
        );

        setBlikTxLimit(
            selectedAccount.limits?.BLIK?.per_transaction_limit ||
            '0.00',
        );

        setBlikDailyLimit(
            selectedAccount.limits?.BLIK?.daily_limit ||
            '0.00',
        );

        if (selectedAccount.account_type === 'JUNIOR') {
            setActiveTab('PREPAID');
        } else if (activeTab === 'PREPAID') {
            setActiveTab('VIRTUAL');
        }
    }, [selectedAccount?.id]);

    const handleSaveLimits = async (
        channel: 'CARD' | 'BLIK',
    ) => {
        setIsSavingLimits(true);

        try {
            const payload =
                channel === 'CARD'
                    ? {
                        account_id: selectedAccount.id,
                        channel: 'CARD',
                        per_transaction_limit: txLimit,
                        daily_limit: dailyLimit,
                    }
                    : {
                        account_id: selectedAccount.id,
                        channel: 'BLIK',
                        per_transaction_limit: blikTxLimit,
                        daily_limit: blikDailyLimit,
                    };

            await api.patch('/accounts/limits/', payload);
            await refreshData();
        } catch (error) {
            console.error('Saving limits failed:', error);
        } finally {
            setIsSavingLimits(false);
        }
    };

    const handleToggleFreeze = async () => {
        if (!activeCardId || isCardActionPending) {
            return;
        }

        const card = selectedAccount?.cards?.find(
            (item: any) => item.id === activeCardId,
        );

        if (!card) {
            return;
        }

        const newStatus =
            card.status === 'FROZEN'
                ? 'ACTIVE'
                : 'FROZEN';

        setIsCardActionPending(true);

        try {
            await api.patch('/cards/manage/', {
                card_id: activeCardId,
                status: newStatus,
            });

            await refreshData();
        } catch (error: any) {
            console.error('Card status update failed:', error);

            alert(
                error.response?.data?.details ||
                error.response?.data?.error ||
                'Could not update the card status.',
            );
        } finally {
            setIsCardActionPending(false);
        }
    };

    const handleActivateCard = async () => {
        if (!activeCardId || isCardActionPending) {
            return;
        }

        setIsCardActionPending(true);

        try {
            await api.post('/cards/activate/', {
                card_id: activeCardId,
            });

            await refreshData();
        } catch (error: any) {
            console.error('Card activation failed:', error);

            alert(
                error.response?.data?.details ||
                error.response?.data?.error ||
                'Could not activate the card.',
            );
        } finally {
            setIsCardActionPending(false);
        }
    };

    const handleArchiveCard = async () => {
        if (!activeCardId || isCardActionPending) {
            return;
        }

        setIsCardActionPending(true);

        try {
            await api.post('/cards/archive/', {
                card_id: activeCardId,
            });

            setIsRemoveModalOpen(false);
            setActiveCardId(null);

            await refreshData();
        } catch (error: any) {
            console.error('Card removal failed:', error);

            alert(
                error.response?.data?.error ||
                error.response?.data?.details ||
                'Could not remove the card.',
            );
        } finally {
            setIsCardActionPending(false);
        }
    };

    const handleIssueCard = async () => {
        if (!selectedAccount || isCardActionPending) {
            return;
        }

        setIsCardActionPending(true);

        try {
            await api.post('/cards/create/', {
                account_id: selectedAccount.id,
                card_type: activeTab,
            });

            await refreshData();
        } catch (error: any) {
            console.error('Card issuing failed:', error);

            alert(
                error.response?.data?.details ||
                error.response?.data?.error ||
                'Could not issue the card.',
            );
        } finally {
            setIsCardActionPending(false);
        }
    };

    if (loading) {
        return (
            <div className="flex-1 h-full flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-[#00FF85]" />
            </div>
        );
    }

    return (
        <>
            <div className="flex-1 p-4 sm:p-5 md:p-6 text-[var(--text-primary)] flex flex-col lg:flex-row gap-5 md:gap-6 w-full">
                {/* LEFT COLUMN: ACCOUNT SELECTOR */}
                <div className="flex w-full lg:w-64 shrink-0 flex-col gap-2">
                    <h2 className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1.5 px-1">
                        Select Account
                    </h2>

                    <div className="flex flex-row lg:flex-col gap-2.5 overflow-x-auto no-scrollbar pb-2 lg:pb-0">
                        {accounts.map((account) => {
                            const isJunior =
                                account.account_type === 'JUNIOR';

                            const isSelected =
                                selectedAccount?.id === account.id;

                            return (
                                <button
                                    key={account.id}
                                    onClick={() => {
                                        setSelectedAccount(account);
                                        setActiveCardId(null);
                                    }}
                                    className={`flex items-center gap-3 shrink-0 lg:shrink w-[220px] lg:w-full p-2.5 rounded-xl transition-all border ${isSelected
                                        ? isJunior
                                            ? 'bg-purple-500/10 border-purple-500/50'
                                            : 'bg-emerald-500/10 border-emerald-500/30'
                                        : 'bg-[var(--bg-surface)] lg:bg-transparent hover:bg-[var(--bg-elevated)] border-[var(--border)] lg:border-transparent'
                                        }`}
                                >
                                    <div
                                        className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center ${isSelected
                                            ? isJunior
                                                ? 'bg-purple-500 text-white'
                                                : 'bg-[#00FF85] text-black'
                                            : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'
                                            }`}
                                    >
                                        <svg
                                            className="w-4 h-4"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                        >
                                            {isJunior ? (
                                                <path
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    strokeWidth={2}
                                                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                                                />
                                            ) : (
                                                <path
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    strokeWidth={2}
                                                    d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                                                />
                                            )}
                                        </svg>
                                    </div>

                                    <div className="text-left flex-1 overflow-hidden flex items-center justify-between gap-2">
                                        <span className="text-sm font-bold truncate">
                                            {isJunior
                                                ? account.owner_first_name
                                                : firstName}
                                        </span>

                                        <span
                                            className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded shrink-0 border ${isJunior
                                                ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                                                : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                                }`}
                                        >
                                            {isJunior ? 'Junior' : 'Current'}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* RIGHT COLUMN: CARD MANAGER */}
                <div className="flex-1 flex flex-col h-full pr-2 pb-6 w-full">
                    {selectedAccount ? (
                        <div className="animate-fadeIn w-full">
                            <CardManager
                                selectedAccount={selectedAccount}
                                activeTab={activeTab}
                                setActiveTab={setActiveTab}
                                activeCardId={activeCardId}
                                setActiveCardId={setActiveCardId}
                                cardsInTab={
                                    selectedAccount.cards?.filter(
                                        (card: any) => card.card_type === activeTab,
                                    ) || []
                                }
                                onIssueCard={handleIssueCard}
                                onFreeze={handleToggleFreeze}
                                onRemove={() => setIsRemoveModalOpen(true)}
                                onActivate={handleActivateCard}
                                onDetails={() => setIsDetailsModalOpen(true)}
                                txLimit={txLimit}
                                dailyLimit={dailyLimit}
                                blikTxLimit={blikTxLimit}
                                blikDailyLimit={blikDailyLimit}
                                setTxLimit={setTxLimit}
                                setDailyLimit={setDailyLimit}
                                setBlikTxLimit={setBlikTxLimit}
                                setBlikDailyLimit={setBlikDailyLimit}
                                onSaveLimits={handleSaveLimits}
                                isSavingLimits={isSavingLimits}
                                isCardActionPending={isCardActionPending}
                                onTopUpClick={() => setIsTopUpModalOpen(true)}
                            />
                        </div>
                    ) : (
                        <div
                            className="text-center p-20"
                            style={{
                                color: 'var(--text-muted)',
                            }}
                        >
                            No account selected.
                        </div>
                    )}
                </div>
            </div>

            <CardDetailsModal
                isOpen={isDetailsModalOpen}
                onClose={() => setIsDetailsModalOpen(false)}
                card={selectedAccount?.cards?.find(
                    (card: any) => card.id === activeCardId,
                )}
            />

            <ConfirmActionModal
                isOpen={isRemoveModalOpen}
                onClose={() => setIsRemoveModalOpen(false)}
                onConfirm={handleArchiveCard}
                loading={isCardActionPending}
                title="Remove card"
                message="Are you sure you want to remove this card? It will be blocked and hidden from your account. Any remaining prepaid balance will be lost."
            />

            <TopUpModal
                isOpen={isTopUpModalOpen}
                onClose={() => setIsTopUpModalOpen(false)}
                cardId={activeCardId}
                onSuccess={() => {
                    setIsTopUpModalOpen(false);
                    refreshData();
                }}
            />
        </>
    );
};

export default Cards;