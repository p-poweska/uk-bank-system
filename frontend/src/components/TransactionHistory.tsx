import React, {
    useCallback,
    useEffect,
    useRef,
    useState,
} from 'react';

import {
    CreditCard,
    Search,
    TrendingDown,
    TrendingUp,
    X,
} from 'lucide-react';

import api from '../api/axios';
import TransactionDetailModal from './TransactionDetailModal';

interface CardPaymentDetails {
    merchant_id: string;
    currency: string;
    card_type: string;
    masked_number: string;
    provider_transaction_id: string;
}

interface Transaction {
    id: number;
    title: string;
    amount: string;
    balance_after: string | null;
    created_at: string;
    type: 'CREDIT' | 'DEBIT';
    account_number: string;
    recipient_name: string | null;
    recipient_account: string | null;
    routing_method: string | null;
    transaction_category?: string | null;
    card_payment?: CardPaymentDetails | null;
}

interface Props {
    accounts: any[];
}

const TransactionHistory: React.FC<Props> = ({
    accounts,
}) => {
    const [
        selectedAccountId,
        setSelectedAccountId,
    ] = useState<string>('');

    const [
        typeFilter,
        setTypeFilter,
    ] = useState<'ALL' | 'CREDIT' | 'DEBIT'>(
        'ALL',
    );

    const [fromDate, setFromDate] = useState('');
    const [toDate, setToDate] = useState('');
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] =
        useState('');

    const [transactions, setTransactions] =
        useState<Transaction[]>([]);

    const [loading, setLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(false);
    const [total, setTotal] = useState(0);

    const [selectedTx, setSelectedTx] =
        useState<Transaction | null>(null);

    const debounceRef = useRef<
        ReturnType<typeof setTimeout> | null
    >(null);

    useEffect(() => {
        if (
            accounts.length > 0 &&
            !selectedAccountId
        ) {
            setSelectedAccountId(
                String(accounts[0].id),
            );
        }
    }, [accounts, selectedAccountId]);

    useEffect(() => {
        if (debounceRef.current) {
            clearTimeout(debounceRef.current);
        }

        debounceRef.current = setTimeout(
            () => {
                setDebouncedSearch(search);
            },
            300,
        );

        return () => {
            if (debounceRef.current) {
                clearTimeout(debounceRef.current);
            }
        };
    }, [search]);

    const buildParams = useCallback(
        (
            currentPage: number,
        ): Record<string, string> => {
            const params: Record<string, string> = {
                page: String(currentPage),
            };

            if (typeFilter !== 'ALL') {
                params.type = typeFilter;
            }

            if (fromDate) {
                params.from = fromDate;
            }

            if (toDate) {
                params.to = toDate;
            }

            if (debouncedSearch) {
                params.search = debouncedSearch;
            }

            return params;
        },
        [
            typeFilter,
            fromDate,
            toDate,
            debouncedSearch,
        ],
    );

    const fetchTransactions = useCallback(
        async () => {
            if (!selectedAccountId) {
                return;
            }

            setLoading(true);

            try {
                const response = await api.get(
                    `/accounts/${selectedAccountId}/transactions/`,
                    {
                        params: buildParams(1),
                    },
                );

                setTransactions(
                    response.data.results,
                );

                setPage(1);
                setTotal(response.data.count);
                setHasMore(
                    Boolean(response.data.next),
                );
            } catch (error) {
                console.error(
                    'Failed to load transactions:',
                    error,
                );
            } finally {
                setLoading(false);
            }
        },
        [
            selectedAccountId,
            buildParams,
        ],
    );

    useEffect(() => {
        fetchTransactions();
    }, [fetchTransactions]);

    const loadMore = async () => {
        if (!selectedAccountId || loading) {
            return;
        }

        const nextPage = page + 1;

        setLoading(true);

        try {
            const response = await api.get(
                `/accounts/${selectedAccountId}/transactions/`,
                {
                    params: buildParams(nextPage),
                },
            );

            setTransactions(
                (currentTransactions) => [
                    ...currentTransactions,
                    ...response.data.results,
                ],
            );

            setPage(nextPage);

            setHasMore(
                Boolean(response.data.next),
            );
        } catch (error) {
            console.error(
                'Failed to load more transactions:',
                error,
            );
        } finally {
            setLoading(false);
        }
    };

    const formatAmount = (
        amount: string,
    ) => {
        const numericAmount =
            parseFloat(amount);

        const formattedAmount =
            new Intl.NumberFormat(
                'en-GB',
                {
                    style: 'currency',
                    currency: 'GBP',
                },
            ).format(
                Math.abs(numericAmount),
            );

        return (
            (numericAmount >= 0
                ? '+'
                : '-') +
            formattedAmount
        );
    };

    const formatBalance = (
        balance: string,
    ) =>
        new Intl.NumberFormat(
            'en-GB',
            {
                style: 'currency',
                currency: 'GBP',
            },
        ).format(
            parseFloat(balance),
        );

    const formatDate = (
        isoDate: string,
    ) =>
        new Date(
            isoDate,
        ).toLocaleDateString(
            'en-GB',
            {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
            },
        );

    const formatTime = (
        isoDate: string,
    ) =>
        new Date(
            isoDate,
        ).toLocaleTimeString(
            'en-GB',
            {
                hour: '2-digit',
                minute: '2-digit',
            },
        );

    const getCardLabel = (
        tx: Transaction,
    ) => {
        if (!tx.card_payment) {
            return null;
        }

        return (
            `${tx.card_payment.card_type} card` +
            ` · ${tx.card_payment.masked_number}`
        );
    };

    return (
        <>
            <div
                className="rounded-3xl p-5 sm:p-6"
                style={{
                    backgroundColor:
                        'var(--bg-surface)',
                    border:
                        '1px solid var(--border)',
                }}
            >
                {/* FILTERS */}
                <div className="flex flex-wrap gap-3 mb-5">
                    {accounts.length > 1 && (
                        <select
                            value={
                                selectedAccountId
                            }
                            onChange={(
                                event,
                            ) =>
                                setSelectedAccountId(
                                    event.target
                                        .value,
                                )
                            }
                            className="px-3 py-2 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#00FF85]/50"
                            style={{
                                backgroundColor:
                                    'var(--bg-base)',
                                border:
                                    '1px solid var(--border)',
                                color:
                                    'var(--text-primary)',
                            }}
                        >
                            {accounts.map(
                                (account) => (
                                    <option
                                        key={
                                            account.id
                                        }
                                        value={
                                            account.id
                                        }
                                    >
                                        {account.account_type ===
                                        'JUNIOR'
                                            ? account.owner_first_name
                                            : 'Current'}{' '}
                                        · ****
                                        {account.account_number?.slice(
                                            -4,
                                        )}
                                    </option>
                                ),
                            )}
                        </select>
                    )}

                    <div
                        className="flex p-1 rounded-xl"
                        style={{
                            backgroundColor:
                                'var(--bg-base)',
                        }}
                    >
                        {(
                            [
                                'ALL',
                                'CREDIT',
                                'DEBIT',
                            ] as const
                        ).map(
                            (
                                transactionType,
                            ) => (
                                <button
                                    key={
                                        transactionType
                                    }
                                    onClick={() =>
                                        setTypeFilter(
                                            transactionType,
                                        )
                                    }
                                    className="px-4 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap"
                                    style={
                                        typeFilter ===
                                        transactionType
                                            ? {
                                                  backgroundColor:
                                                      'var(--bg-elevated)',
                                                  color:
                                                      'var(--text-primary)',
                                              }
                                            : {
                                                  color:
                                                      'var(--text-muted)',
                                              }
                                    }
                                >
                                    {transactionType ===
                                    'ALL'
                                        ? 'All'
                                        : transactionType ===
                                            'CREDIT'
                                          ? 'Money in'
                                          : 'Money out'}
                                </button>
                            ),
                        )}
                    </div>

                    <div className="flex gap-2 items-center flex-wrap">
                        <input
                            type="date"
                            value={fromDate}
                            onChange={(
                                event,
                            ) =>
                                setFromDate(
                                    event.target
                                        .value,
                                )
                            }
                            className="px-3 py-2 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#00FF85]/50"
                            style={{
                                backgroundColor:
                                    'var(--bg-base)',
                                border:
                                    '1px solid var(--border)',
                                color:
                                    'var(--text-primary)',
                            }}
                        />

                        <span
                            className="text-xs"
                            style={{
                                color:
                                    'var(--text-muted)',
                            }}
                        >
                            to
                        </span>

                        <input
                            type="date"
                            value={toDate}
                            onChange={(
                                event,
                            ) =>
                                setToDate(
                                    event.target
                                        .value,
                                )
                            }
                            className="px-3 py-2 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#00FF85]/50"
                            style={{
                                backgroundColor:
                                    'var(--bg-base)',
                                border:
                                    '1px solid var(--border)',
                                color:
                                    'var(--text-primary)',
                            }}
                        />

                        {(fromDate ||
                            toDate) && (
                            <button
                                onClick={() => {
                                    setFromDate(
                                        '',
                                    );

                                    setToDate('');
                                }}
                                className="text-xs px-2 py-1 rounded-lg"
                                style={{
                                    color:
                                        'var(--text-muted)',
                                    backgroundColor:
                                        'var(--bg-base)',
                                }}
                            >
                                Clear
                            </button>
                        )}
                    </div>

                    <div className="relative flex-1 min-w-48">
                        <Search
                            size={14}
                            className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                            style={{
                                color:
                                    'var(--text-muted)',
                            }}
                        />

                        <input
                            type="text"
                            placeholder="Search by title, recipient or merchant…"
                            value={search}
                            onChange={(
                                event,
                            ) =>
                                setSearch(
                                    event.target
                                        .value,
                                )
                            }
                            className="w-full pl-8 pr-8 py-2 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#00FF85]/50"
                            style={{
                                backgroundColor:
                                    'var(--bg-base)',
                                border:
                                    '1px solid var(--border)',
                                color:
                                    'var(--text-primary)',
                            }}
                        />

                        {search && (
                            <button
                                onClick={() =>
                                    setSearch('')
                                }
                                className="absolute right-2.5 top-1/2 -translate-y-1/2"
                                style={{
                                    color:
                                        'var(--text-muted)',
                                }}
                            >
                                <X
                                    size={
                                        14
                                    }
                                />
                            </button>
                        )}
                    </div>
                </div>

                {total > 0 && (
                    <p
                        className="text-xs mb-4"
                        style={{
                            color:
                                'var(--text-muted)',
                        }}
                    >
                        {total}{' '}
                        transaction
                        {total !== 1
                            ? 's'
                            : ''}

                        {debouncedSearch && (
                            <span>
                                {' '}
                                matching{' '}
                                <strong>
                                    "
                                    {
                                        debouncedSearch
                                    }
                                    "
                                </strong>
                            </span>
                        )}
                    </p>
                )}

                {/* TRANSACTION LIST */}
                {loading &&
                transactions.length ===
                    0 ? (
                    <div className="flex justify-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-[#00FF85]" />
                    </div>
                ) : transactions.length ===
                  0 ? (
                    <div className="text-center py-12">
                        <p
                            className="text-sm"
                            style={{
                                color:
                                    'var(--text-muted)',
                            }}
                        >
                            {debouncedSearch
                                ? `No transactions matching "${debouncedSearch}".`
                                : 'No transactions found.'}
                        </p>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {transactions.map(
                            (tx) => {
                                const isCredit =
                                    tx.type ===
                                    'CREDIT';

                                const isCardPayment =
                                    tx.transaction_category ===
                                        'CARD_PAYMENT' &&
                                    Boolean(
                                        tx.card_payment,
                                    );

                                const cardLabel =
                                    getCardLabel(
                                        tx,
                                    );

                                return (
                                    <button
                                        key={
                                            tx.id
                                        }
                                        onClick={() =>
                                            setSelectedTx(
                                                tx,
                                            )
                                        }
                                        className="w-full flex items-center gap-4 p-3 sm:p-4 rounded-2xl transition-all text-left hover:scale-[1.01] active:scale-[0.99]"
                                        style={{
                                            backgroundColor:
                                                'var(--bg-base)',
                                            border:
                                                '1px solid var(--border)',
                                        }}
                                    >
                                        <div
                                            className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                                                isCardPayment
                                                    ? 'bg-blue-500/10 text-blue-400'
                                                    : isCredit
                                                      ? 'bg-emerald-500/10 text-emerald-400'
                                                      : 'bg-red-500/10 text-red-400'
                                            }`}
                                        >
                                            {isCardPayment ? (
                                                <CreditCard
                                                    size={
                                                        16
                                                    }
                                                />
                                            ) : isCredit ? (
                                                <TrendingUp
                                                    size={
                                                        16
                                                    }
                                                />
                                            ) : (
                                                <TrendingDown
                                                    size={
                                                        16
                                                    }
                                                />
                                            )}
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <p
                                                className="text-sm font-semibold truncate"
                                                style={{
                                                    color:
                                                        'var(--text-primary)',
                                                }}
                                            >
                                                {
                                                    tx.title
                                                }
                                            </p>

                                            <p
                                                className="text-xs mt-0.5 truncate"
                                                style={{
                                                    color:
                                                        'var(--text-muted)',
                                                }}
                                            >
                                                {formatDate(
                                                    tx.created_at,
                                                )}{' '}
                                                ·{' '}
                                                {formatTime(
                                                    tx.created_at,
                                                )}

                                                {cardLabel
                                                    ? ` · ${cardLabel}`
                                                    : tx.recipient_name
                                                      ? ` · ${tx.recipient_name}`
                                                      : ''}
                                            </p>
                                        </div>

                                        <div className="text-right shrink-0">
                                            <p
                                                className={`text-sm font-black ${
                                                    isCredit
                                                        ? 'text-emerald-400'
                                                        : 'text-red-400'
                                                }`}
                                            >
                                                {formatAmount(
                                                    tx.amount,
                                                )}
                                            </p>

                                            {tx.balance_after !==
                                                null && (
                                                <p
                                                    className="text-[10px] mt-0.5"
                                                    style={{
                                                        color:
                                                            'var(--text-muted)',
                                                    }}
                                                >
                                                    Bal:{' '}
                                                    {formatBalance(
                                                        tx.balance_after,
                                                    )}
                                                </p>
                                            )}
                                        </div>
                                    </button>
                                );
                            },
                        )}
                    </div>
                )}

                {hasMore && (
                    <div className="mt-4 text-center">
                        <button
                            onClick={
                                loadMore
                            }
                            disabled={
                                loading
                            }
                            className="px-6 py-2.5 rounded-xl text-sm font-bold transition-colors disabled:opacity-50"
                            style={{
                                backgroundColor:
                                    'var(--bg-elevated)',
                                color:
                                    'var(--text-primary)',
                                border:
                                    '1px solid var(--border)',
                            }}
                        >
                            {loading
                                ? 'Loading...'
                                : 'Load more'}
                        </button>
                    </div>
                )}
            </div>

            <TransactionDetailModal
                isOpen={Boolean(
                    selectedTx,
                )}
                onClose={() =>
                    setSelectedTx(
                        null,
                    )
                }
                transaction={
                    selectedTx
                }
            />
        </>
    );
};

export default TransactionHistory;