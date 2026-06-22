# Przewodnik prezentacji — Lyo Bank + 5 systemów płatności

Bank (`uk-bank-system`) zintegrowany z 5 niezależnymi systemami:
**UKPS** (CHAPS/FPS/BACS), **SWIFT** (międzynarodowe), **KLIK**, **Karty**.
Wysyła **i odbiera** płatności, a wszystko widać po obu stronach.

---

## 1. Adresy i logowania

| Co | URL | Login / hasło |
|----|-----|---------------|
| **Aplikacja banku** | http://localhost:5173 | `ukps_test@example.com` / `Testpass123` |
| Drugie konto (do KLIK P2P) | http://localhost:5173 | `klik_rcpt@example.com` / `Testpass123` |
| **Django admin** (rekordy banku) | http://localhost:8001/admin/ | `admin@ukbank.com` / `admin12345` |
| **pgAdmin** (baza) | http://localhost:5050 | `admin@ukbank.com` / `admin12345` |
| **Podgląd UKPS** | http://localhost:4173 | klucz API (patrz niżej) |
| **Dashboard SWIFT** | http://localhost:3000 | — |
| **UI agenta KLIK** | http://localhost:5175 | — |
| **Panel Kart** | http://localhost:3072 | — |

**pgAdmin — podłączenie serwera bazy** (po zalogowaniu: *Servers → Register → Server → Connection*):
host `db`, port `5432`, baza `uk_bank_db`, user `bank_admin`, hasło `bank_password`.

**Konta testowe w aplikacji:**
- Konto główne: `72844746` (CURRENT, GBP) — nadawca wszystkich przelewów.
- Konto odbiorcy KLIK: `61242659` (alias telefonu `+447900000002`).

---

## 2. Dane do przelewów

### Przelewy krajowe (zakładka *External Transfer*) — UKPS
Wpisz **Account number (IBAN)** + pojawi się pole **BIC**.

| Schemat | Bank | IBAN | BIC | Kwota | Zachowanie |
|---------|------|------|-----|-------|------------|
| **FPS** | Barclays | `GB00BARC20000012345678` | `BARCGB2L` | < £250 000, np. £200 | natychmiast (SETTLED) |
| **CHAPS** | HSBC | `GB00HSBC40000012345678` | `HSBCGB44` | np. £5000 | same-day, **tylko 06:00–18:00 UTC** |
| **BACS** | Lloyds | `GB00LLOY30000012345678` | `LLOYGB21` | np. £150 | wsadowy → PENDING, rozlicza się w cyklu |

> Inne banki seed: Lloyds `LLOYGB21` (30-00-00). Odbiorca **musi** być bankiem seed.

### Przelewy międzynarodowe — SWIFT
Wpisz **IBAN spoza GB** → formularz sam przełączy sieć na **SWIFT**, wybierz walutę i wpisz BIC.

| Bank | IBAN (konto istniejące) | BIC | Waluta |
|------|-------------------------|-----|--------|
| Bank USA | `US123456789012345678901234` | `USBKUS01XXX` | USD |
| Bank DE | `DE89370400440532013000` | `DEBKDE01XXX` | EUR |
| Bank PL | `PL62109010140000071219812875` | `PLBKPL01XXX` | PLN |

Bank przelicza GBP → walutę docelową (kurs stały) i dolicza prowizję.

### KLIK
- **Alias:** numer telefonu, np. `+447900000001` (Twój), `+447900000002` (odbiorca).
- **P2P:** wyślij na `+447900000002`, np. £30.
- **Kod:** generujesz 6-cyfrowy kod (ważny 120 s).

### Karta
- Typ: `VIRTUAL` (lub `PREPAID`), tworzysz na koncie `72844746`.

---

## 3. Scenariusz prezentacji (krok po kroku)

### A. Logowanie i konta
1. Otwórz http://localhost:5173, zaloguj `ukps_test@example.com` / `Testpass123`.
2. Pokaż Dashboard — konto `72844746` i saldo.

### B. Przelew krajowy FPS (natychmiastowy)
1. *Payments → New Transfer → External Transfer*.
2. Recipient: `Barclays Payee`, IBAN `GB00BARC20000012345678`, BIC `BARCGB2L`, sieć **FPS**, kwota `200`.
3. Zatwierdź → saldo spada od razu, przelew **Completed**.
4. **Weryfikacja:** http://localhost:4173 (klucz FPS) → przelew widoczny w sieci FPS.

### C. Przelew CHAPS (wysokokwotowy, tylko w godzinach 06–18 UTC)
1. To samo, ale IBAN `GB00HSBC40000012345678`, BIC `HSBCGB44`, sieć **CHAPS**, kwota `5000`.
2. **Weryfikacja:** podgląd UKPS (klucz CHAPS).

### D. Przelew BACS (wsadowy)
1. IBAN `GB00LLOY30000012345678`, BIC `LLOYGB21`, sieć **BACS**, kwota `150`.
2. Pokaż status **Pending** — *„rozliczy się w cyklu"*.
3. (Opcjonalnie domknij cykl, by pokazać przejście w **Completed** — patrz sekcja 5.)

### E. Przelew międzynarodowy SWIFT (z przewalutowaniem)
1. IBAN `US123456789012345678901234`, BIC `USBKUS01XXX`, waluta **USD**, kwota `100`.
2. Pokaż przeliczenie GBP→USD + prowizję.
3. **Weryfikacja:** http://localhost:3000 → komunikat SWIFT + UETR na dashboardzie.

### F. Odbieranie płatności (przychodzące)
1. W terminalu wyślij przelew z innego banku **do nas** (`LYOBGB2L`):
   ```bash
   curl -s -X POST http://localhost:8421/v1/payments/fps \
     -H "Authorization: Bearer ak_barcgb2l_dev" -H "Content-Type: application/json" \
     -d '{"msg_id":"DEMO-IN-1","receiver_bic":"LYOBGB2L","receiver_sort_code":"10-20-30","amount":250.00}'
   ```
2. Wróć do aplikacji → **saldo +£250 i powiadomienie** (bank odebrał z sieci przez listener SSE).

### G. KLIK
1. Zakładka **Klik** → *Zarejestruj alias* `+447900000001`.
2. *Wygeneruj kod* — pokaż 6-cyfrowy kod.
3. *P2P send* → telefon `+447900000002`, kwota `30` → **Completed**.
4. **Weryfikacja:** http://localhost:5175 (UI agenta) lub:
   ```bash
   docker exec klik-payments-web-1 python manage.py shell -c "from codes.models import Transaction; [print(t.id,t.status,t.zone) for t in Transaction.objects.all()[:10]]"
   ```

### H. Karta
1. Zakładka **Cards** → *Utwórz kartę* (VIRTUAL) na koncie `72844746`.
2. Pokaż wydaną kartę (zamaskowany numer).
3. **Weryfikacja:** http://localhost:3072 (panel kart) — karta widoczna po stronie systemu kart.

### I. Pełna ścieżka audytowa
- http://localhost:8001/admin/ (`admin@ukbank.com`/`admin12345`) → **UKPS payments** (in/out), **Klik payments**, **Card captures**, **Transfers**, **Transactions**.

---

## 4. Jak sprawdzić, że płatność przeszła po drugiej stronie

| System | Gdzie | Jak |
|--------|-------|-----|
| **UKPS** | http://localhost:4173 | wpisz klucz danego schematu (komenda niżej) |
| | terminal | `curl http://localhost:8421/v1/payments/fps -H "Authorization: Bearer <klucz-FPS>"` |
| **SWIFT** | http://localhost:3000 | dashboard z komunikatami + UETR |
| **KLIK** | http://localhost:5175 | UI agenta / lub shell (komenda w kroku G) |
| **Karty** | http://localhost:3072 | panel autoryzacji i settlementów |
| **Bank (wszystko)** | http://localhost:8001/admin/ | rekordy wszystkich płatności |

**Klucze API banku do podglądu UKPS** (osobny na schemat):
```bash
docker exec uk-bank-system-backend-1 python manage.py ukps_keys
```

---

## 5. Polecenia pomocnicze

**Domknięcie cyklu BACS** (żeby przelew BACS pokazał *Completed*):
```bash
curl -s -X POST http://localhost:8422/v1/payments/bacs/cycle/close -H "Authorization: Bearer ak_barcgb2l_dev"
docker exec uk-bank-system-backend-1 python manage.py ukps_reconcile
```
(albo poczekaj — listener domyka oczekujące BACS automatycznie co 30 s)

**Stan wszystkich kontenerów:** `docker ps`

---

## 6. Kolejność uruchamiania (gdyby trzeba było wszystko zrestartować)

⚠️ **Kolejność ma znaczenie** (sieci współdzielone). KLIK **musi** iść z dev-compose.

```bash
# 1. Karty (tworzy sieć cards-backend)
cd ~/Documents/GitHub/Karty-Platnicze-Aplikacje-Biznesowe && docker compose up -d

# 2. UK Payment Systems (tworzy chaps_klik)
cd ~/Documents/GitHub/uk-payment-systems && docker compose up -d

# 3. KLIK — KONIECZNIE dev-compose (inaczej 'web' padnie)
cd ~/Documents/GitHub/KLIK-payments && make dev-d

# 4. Bank
cd ~/Documents/GitHub/uk-bank-system && docker compose up -d

# 5. SWIFT
cd ~/Documents/GitHub/SWIFT-Aplikacje-Biznesowe && docker compose up -d
```

---

## 7. Rozwiązywanie problemów

| Objaw | Przyczyna | Naprawa |
|-------|-----------|---------|
| CHAPS „closed: opens at 06:00" | poza godzinami 06–18 UTC | użyj FPS, albo CHAPS w dzień |
| „not a participating bank" | zły BIC odbiorcy | użyj BIC seed (BARCGB2L/HSBCGB44/LLOYGB21) |
| KLIK `web` ciągle pada | KLIK odpalony bez dev-compose | `cd KLIK-payments && make dev-d` |
| „Could not issue card" | uszkodzony stan sieci `cards-backend` | reset sieci (niżej) |
| Płatność nie pokazuje się w podglądzie UKPS | zły klucz API | użyj klucza ze schematu (`ukps_keys`) |

**Reset sieci kart** (gdy karty się wysypią):
```bash
cd ~/Documents/GitHub/uk-bank-system && docker compose down
cd ~/Documents/GitHub/Karty-Platnicze-Aplikacje-Biznesowe && docker compose down
docker network rm cards-backend 2>/dev/null
docker compose up -d
cd ~/Documents/GitHub/uk-bank-system && docker compose up -d
```

> **Wskazówka:** przed prezentacją odpal wszystko raz i **nie restartuj stacków bez potrzeby** — sieci kart bywają wrażliwe na wielokrotne przebudowy.

---

## 8. Pointa prezentacji

Bank realizuje przelewy przez **5 niezależnych systemów** (CHAPS, FPS, BACS, SWIFT, KLIK + karty),
**wysyła i odbiera** płatności, a każda z nich jest widoczna **jednocześnie** po stronie banku
i po stronie danego systemu rozliczeniowego — to dowód realnej, dwustronnej integracji.
