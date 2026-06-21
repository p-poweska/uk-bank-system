import React from 'react';
import {
  Plus,
  Eye,
  Snowflake,
  ShieldCheck,
  Power,
  Trash2,
} from 'lucide-react';

interface Props {
  selectedAccount: any;
  activeTab: 'VIRTUAL' | 'PHYSICAL' | 'PREPAID';
  setActiveTab: (t: any) => void;
  activeCardId: string | null;
  setActiveCardId: (id: string | null) => void;
  cardsInTab: any[];
  onIssueCard: () => void;
  onFreeze: () => void;
  onRemove: () => void;
  onActivate: () => void;
  onDetails: () => void;
  onTopUpClick: () => void;
  isCardActionPending: boolean;
}

const CardManager: React.FC<Props> = ({
  selectedAccount,
  activeTab,
  setActiveTab,
  activeCardId,
  setActiveCardId,
  cardsInTab,
  onIssueCard,
  onFreeze,
  onRemove,
  onActivate,
  onDetails,
  onTopUpClick,
  isCardActionPending,
}) => {
  const activeCard = cardsInTab.find((card) => card.id === activeCardId);
  const isJunior = selectedAccount?.account_type === 'JUNIOR';

  const canActivate =
    activeCard &&
    activeCard.card_type !== 'VIRTUAL' &&
    activeCard.status === 'SHIPPING';

  const canToggleFreeze =
    activeCard &&
    (
      activeCard.status === 'ACTIVE' ||
      activeCard.status === 'FROZEN'
    );

  const canTopUp =
    activeCard &&
    activeCard.card_type === 'PREPAID' &&
    activeCard.status === 'ACTIVE';

 
  const canRemove =
  activeCard &&
  (
    activeCard.status === 'ACTIVE' ||
    activeCard.status === 'FROZEN' ||
    activeCard.status === 'SHIPPING'
  );

  const renderCard = (card: any) => (
    <div
      key={card.id}
      onClick={() => setActiveCardId(card.id)}
      className={`
        w-full max-w-[360px] mx-auto aspect-[1.58/1] rounded-2xl p-4 flex flex-col justify-between shadow-xl cursor-pointer transition-all duration-300
        border-[2px] ${activeCardId === card.id
          ? 'border-white shadow-[0_0_20px_rgba(255,255,255,0.15)] scale-[1.02]'
          : 'border-transparent opacity-60 hover:opacity-100'
        }
        ${card.status === 'FROZEN'
          ? 'bg-gradient-to-br from-slate-800 to-slate-900'
          : card.card_type === 'VIRTUAL'
            ? 'bg-gradient-to-br from-emerald-500 to-teal-700'
            : card.card_type === 'PHYSICAL'
              ? 'bg-gradient-to-br from-gray-600 to-gray-800'
              : 'bg-gradient-to-br from-purple-500 to-indigo-600'
        }
      `}
    >
      <div className="flex justify-between items-start">
        <div className="bg-black/20 backdrop-blur-md px-2 py-1 rounded text-[8px] font-black text-white uppercase tracking-wider">
          {card.status}
        </div>

        {card.card_type === 'PREPAID' && (
          <div className="text-right">
            <div className="text-[8px] text-white/70 uppercase font-bold tracking-widest mb-0.5">
              Card Balance
            </div>
            <div className="text-sm font-black text-white">
              £{parseFloat(card.prepaid_balance || '0').toFixed(2)}
            </div>
          </div>
        )}
      </div>

      <div className="mt-auto">
        <div className="text-white font-mono tracking-widest text-base sm:text-lg mb-1.5 drop-shadow-md">
          {card.masked_number}
        </div>

        <div className="flex justify-between items-end text-[8px] text-white/90 font-bold uppercase tracking-widest">
          <span className="truncate pr-2">
            {card.cardholder_name}
          </span>

          <span className="shrink-0">
            {card.expiry_date}
          </span>
        </div>
      </div>
    </div>
  );

  const renderAddCard = () => (
    <button
      onClick={onIssueCard}
      disabled={isCardActionPending}
      className="w-full max-w-[360px] mx-auto aspect-[1.58/1] border-2 border-dashed border-[var(--border)] rounded-2xl flex flex-col items-center justify-center hover:border-[var(--text-primary)] hover:text-[var(--text-primary)] text-[var(--text-muted)] transition-colors group disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <div className="w-10 h-10 sm:w-12 sm:h-12 bg-gray-800 group-hover:bg-white/10 rounded-full flex items-center justify-center mb-2 transition-colors">
        <Plus className="w-5 h-5 sm:w-6 sm:h-6" />
      </div>

      <span className="text-[9px] font-black uppercase tracking-widest">
        Add {isJunior ? 'PREPAID' : activeTab}
      </span>
    </button>
  );

  return (
    // ZMIANA 1: Dodano 'max-w-4xl mx-auto', aby panel nie zajmował całej szerokości ekranu
    <div className="max-w-4xl mx-auto w-full mb-4">
      {/* LEFT COLUMN: CARDS */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-3xl p-5 md:p-6 flex flex-col shadow-lg min-h-[340px] w-full overflow-hidden">
        
        {/* HEADER / TABS */}
        <div className="flex flex-wrap justify-between items-center border-b border-[var(--border)] pb-3.5 mb-5 gap-3">
          <div className="flex gap-4 sm:gap-6 overflow-x-auto no-scrollbar w-full sm:w-auto">
            {isJunior ? (
              <div className="text-[9px] sm:text-[10px] font-black uppercase tracking-[0.2em] text-[var(--text-primary)] relative pb-1.5 whitespace-nowrap">
                PREPAID CARD
                <div className="absolute bottom-0 left-0 w-full h-[2px] bg-purple-500 shadow-[0_0_10px_rgba(168,85,247,0.5)]" />
              </div>
            ) : (
              (['VIRTUAL', 'PHYSICAL', 'PREPAID'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`text-[9px] sm:text-[10px] font-black uppercase tracking-[0.2em] transition-all relative pb-1.5 whitespace-nowrap ${activeTab === tab
                    ? 'text-[var(--text-primary)]'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                    }`}
                >
                  {tab}

                  {activeTab === tab && (
                    <div className="absolute bottom-0 left-0 w-full h-[2px] bg-[#00FF85] shadow-[0_0_10px_rgba(0,255,133,0.5)]" />
                  )}
                </button>
              ))
            )}
          </div>

          <div className="text-[9px] text-[var(--text-muted)] font-bold bg-[var(--bg-elevated)] px-2 py-1 rounded whitespace-nowrap self-start sm:self-auto">
            {cardsInTab.length} / {isJunior ? '1' : '2'} cards
          </div>
        </div>

        {/* CARD CONTAINER */}
        <div className="flex-1 flex flex-col justify-center mb-5 w-full">
          {isJunior ? (
            <div className="w-full flex justify-center">
              {cardsInTab.length > 0
                ? cardsInTab.map(renderCard)
                : renderAddCard()}
            </div>
          ) : (
            // ZMIANA 2: Użyto 'flex flex-wrap justify-center' zamiast 'grid', aby karty i przycisk trzymały swój rozmiar
            <div className="flex flex-wrap justify-center gap-6 w-full">
              {cardsInTab.map(renderCard)}
              {cardsInTab.length < 2 && renderAddCard()}
            </div>
          )}
        </div>

        {/* ACTION BUTTONS */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mt-auto pt-4 border-t border-[var(--border)]/50">
          {activeCard?.card_type === 'PREPAID' && (
            <button
              onClick={onTopUpClick}
              disabled={!canTopUp || isCardActionPending}
              className={`p-2.5 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-[8px] sm:text-[9px] font-bold uppercase tracking-widest text-center ${canTopUp && !isCardActionPending
                ? 'bg-[var(--bg-base)] hover:bg-[#00FF85]/10 border-[var(--border)] text-gray-400 hover:text-[#00FF85] cursor-pointer'
                : 'bg-[var(--bg-base)]/40 border-[var(--border)] text-[var(--text-muted)] opacity-40 cursor-not-allowed'
                }`}
            >
              <Plus
                className="w-4 h-4 sm:w-[16px] sm:h-[16px]"
                color={activeCard ? '#00FF85' : 'currentColor'}
              />
              Top Up
            </button>
          )}

          <button
            onClick={onDetails}
            disabled={!activeCard}
            className={`p-2.5 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-[8px] sm:text-[9px] font-bold uppercase tracking-widest text-center ${activeCard
              ? 'bg-[var(--bg-base)] hover:bg-white/5 border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer'
              : 'bg-[var(--bg-base)]/40 border-[var(--border)] text-[var(--text-muted)] opacity-40 cursor-not-allowed'
              }`}
          >
            <Eye
              className="w-4 h-4 sm:w-[16px] sm:h-[16px] text-gray-400"
              color={
                activeCard
                  ? isJunior
                    ? '#c084fc'
                    : '#34d399'
                  : 'currentColor'
              }
            />
            Details
          </button>
          
          {canActivate && (
            <button
              onClick={onActivate}
              disabled={isCardActionPending}
              className="p-2.5 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-[8px] sm:text-[9px] font-bold uppercase tracking-widest text-center bg-[var(--bg-base)] hover:bg-[#00FF85]/10 border-[var(--border)] text-gray-400 hover:text-[#00FF85] cursor-pointer"
            >
              <Power className="w-4 h-4 sm:w-[16px] sm:h-[16px]" />
              Activate
            </button>
          )}

          <button
            onClick={onFreeze}
            disabled={!canToggleFreeze || isCardActionPending}
            className={`p-2.5 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-[8px] sm:text-[9px] font-bold uppercase tracking-widest text-center ${canToggleFreeze && !isCardActionPending
              ? activeCard.status === 'FROZEN'
                ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                : 'bg-[var(--bg-base)] hover:bg-white/5 border-[var(--border)] text-gray-400 hover:text-white'
              : 'bg-[var(--bg-base)]/40 border-[var(--border)] text-[var(--text-muted)] opacity-40 cursor-not-allowed'
              }`}
          >
            <Snowflake
              className="w-4 h-4 sm:w-[16px] sm:h-[16px]"
              color={
                activeCard?.status === 'FROZEN'
                  ? '#60a5fa'
                  : 'currentColor'
              }
            />
            {activeCard?.status === 'FROZEN'
              ? 'Unfreeze'
              : 'Freeze'}
          </button>
          
          <button
            onClick={onRemove}
            disabled={!canRemove || isCardActionPending}
            className={`p-2.5 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all text-[8px] sm:text-[9px] font-bold uppercase tracking-widest text-center ${canRemove && !isCardActionPending
                ? 'bg-[var(--bg-base)] hover:bg-red-500/10 border-[var(--border)] text-gray-400 hover:text-red-400 cursor-pointer'
                : 'bg-[var(--bg-base)]/40 border-[var(--border)] text-[var(--text-muted)] opacity-40 cursor-not-allowed'
              }`}
          >
            <Trash2 className="w-4 h-4 sm:w-[16px] sm:h-[16px]" />
            Remove
          </button>
        </div>
      </div>
    </div>
  );
};

export default CardManager;