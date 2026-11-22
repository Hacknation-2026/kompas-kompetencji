# Tutorial: Manualne testy End-to-End (E2E) – Kompas Kompetencji

Poniższa instrukcja przeprowadza krok po kroku przez uruchomienie środowiska, konfigurację bazy danych (SQLite lub PostgreSQL + Alembic), budowę bazy wiedzy RAG oraz pełny manualny test obu ścieżek oceny w przeglądarce i API (PowerShell / Windows).

---

## 1. Przygotowanie środowiska i zależności

### Wariant podstawowy (SQLite / tryb `dev`)
```powershell
# Aktywacja lub synchronizacja środowiska
uv sync --extra dev

# Opcjonalnie (embeddingi neuronowe dla HybridRetriever):
uv sync --extra dev --extra ml
```

### Wariant produkcyjny (PostgreSQL + Alembic)
```powershell
uv sync --extra dev --extra prod
```

---

## 2. Konfiguracja i inicjalizacja bazy danych

### Wariant A: Szybki start na SQLite (bez Dockera/PostgreSQL)
Repozytorium ma wbudowany provider `sqlite` (z biblioteki standardowej Pythona). Baza utworzy się automatycznie przy starcie aplikacji w pliku `data/runtime/kompas.db`:
```powershell
$env:KOMPAS__REPOSITORY__PROVIDER = "sqlite"
$env:KOMPAS__REPOSITORY__PARAMS__PATH = "data/runtime/kompas.db"
```

### Wariant B: PostgreSQL + migracje Alembic
1. Uruchom bazę PostgreSQL (np. przez Docker):
```powershell
docker run --name kompas-pg -e POSTGRES_USER=kompas -e POSTGRES_PASSWORD=kompas -e POSTGRES_DB=kompas -p 5432:5432 -d postgres:16
```
2. Ustaw zmienne środowiskowe i wykonaj migrację schematu (`001_initial_schema`):
```powershell
$env:KOMPAS_DATABASE_URL = "postgresql+psycopg://kompas:kompas@localhost:5432/kompas"
.venv\Scripts\alembic.exe upgrade head
```
3. Włącz providera `postgres`:
```powershell
# W trybie dev z PostgreSQL:
$env:KOMPAS__REPOSITORY__PROVIDER = "postgres"
$env:KOMPAS__REPOSITORY__PARAMS__DSN = $env:KOMPAS_DATABASE_URL

# Lub pełny tryb prod (wymaga też sekretu JWT):
$env:KOMPAS_ENV = "prod"
$env:KOMPAS__SECURITY__JWT_SECRET = "bardzo-dlugi-losowy-sekret-produkcyjny-min-32-znaki"
```

---

## 3. Przygotowanie bazy wiedzy RAG i lokalnego LLM (Bielik)

### Budowa indeksu chunków
```powershell
.venv\Scripts\python.exe -m scripts.build_knowledge_base
```
*(Plik wynikowy zapisze się w `models/index/chunks.json`.)*

### Model LLM
- **Z lokalnym Bielikiem (Ollama):** upewnij się, że Ollama działa i ma pobrany model:
  ```powershell
  ollama pull hf.co/speakleash/Bielik-4.5B-v3.0-Instruct-GGUF
  ollama serve
  ```
- **Bez Ollamy (szybki tryb offline/ekstrakcyjny do testów UI):**
  ```powershell
  $env:KOMPAS__LLM__PROFILE = "extractive"
  $env:KOMPAS__EMBEDDINGS__PROFILE = "hashing"
  ```

---

## 4. Uruchomienie aplikacji

```powershell
$env:KOMPAS_ENV = "dev"
.venv\Scripts\python.exe -m kompas
```
Aplikacja wystartuje pod adresem:
- **Interfejs webowy (UI):** `http://127.0.0.1:8000/`
- **Dokumentacja OpenAPI (Swagger):** `http://127.0.0.1:8000/api/v1/docs`

---

## 5. Manualny test E2E w przeglądarce

### Krok 0: Weryfikacja blokady smartfonów
1. Otwórz `http://127.0.0.1:8000/` w Chrome/Edge.
2. Włącz DevTools (`F12`) → widok mobilny o szerokości `< 768px` (np. `390x844`).
3. **Oczekiwany efekt:** zamiast formularza logowania widoczny jest komunikat o dostępności wyłącznie na komputerze lub tablecie. Wyłącz tryb mobilny.

### Krok 1: Logowanie jako Przełożony
1. Kliknij chip **Przełożony (Anna K.)** (`przelozony` / `demo-password-1`).
2. Sprawdź, że na liście podległych pracowników są m.in. **Jan Kowalski** (`emp-1`) i **Ewa Majewska** (`emp-2`).

### Krok 2: Ścieżka 1 – Pierwsza ocena (`emp-1`: Jan Kowalski)
1. W karcie **Ścieżka 1: Pierwsza ocena** wybierz **Jan Kowalski** i kliknij **Rozpocznij ocenę**.
2. **Terminy i przedłużenie:** kliknij **Terminy i przedłużenie** w nagłówku kreatora → wybierz etap `Sprawozdanie ocenianego`, ustaw nową datę i podaj powód (np. `Usprawiedliwiona nieobecność`), kliknij **Przedłuż termin**. Sprawdź, że wpis pojawił się w historii przedłużeń.
3. **Rozmowa wstępna:** kliknij **Potwierdź rozmowę wstępną i przejdź dalej →**.
4. **Sprawozdanie ocenianego (Załącznik nr 3):**
   - Wpisz okres `5` miesięcy → kliknij zapis → **oczekiwany błąd walidacji** (`>= 7` miesięcy).
   - Zmień okres na `8` miesięcy, uzupełnij pola: *Wykonywane zadania*, *Napotkane trudności*, *Nabyte umiejętności*, *Propozycje usprawnień* i przejdź dalej.
5. **Ocena kompetencji (skala 3 / 5 / 7):**
   - Dla każdego z 5 elementów wybierz zachowanie przy wskaźnikach, wpisz opcjonalny dowód **STAR** (*Sytuacja – działanie – rezultat*), kliknij **Zapisz kryterium**, sprawdź **Sugestię systemu**, a następnie wybierz ostateczną ocenę cząstkową i zapisz.
   - Kliknij **Zakończ ocenę kryteriów i przejdź dalej →**.
6. **Rozmowa oceniająca:** przejdź dalej.
7. **Zakończenie oceny:**
   - Wybierz egzamin: **Niezaliczony** → kliknij **Oblicz wynik oceny** (bez uzasadnienia próba zamknięcia kroku zostanie zablokowana; wynik pokaże `OCENA NEGATYWNA`).
   - Zmień egzamin na **Zaliczony**, oblicz wynik (`OCENA POZYTYWNA`), zatwierdź krok.
8. **Zapoznanie z oceną:** pobierz **PDF** oraz **podgląd HTML**, kliknij **Zakończ proces oceny ✓**.

### Krok 3: Ścieżka 2 – Ocena okresowa (`emp-2`: Ewa Majewska)
1. Wróć na **Ścieżki oceny**.
2. W karcie **Ścieżka 2: Ocena okresowa** wybierz **Ewa Majewska** (pozostaw *Dobór automatyczny*), kliknij **Rozpocznij ocenę**.
3. **Analiza OSP:** wgraj plik `.docx`/`.pdf`/`.txt` z opisem stanowiska (lub wklej tekst o analizie prawa AI/UE) i kliknij **Analizuj OSP** → system wskaże **Arkusz C** i zarekomenduje kryteria dodatkowe. Przejdź dalej.
4. **Ustalenie kryteriów (Część I):** zaznacz 1–3 kryteria dodatkowe, wpisz cel i zatwierdź.
5. **Ocena kryteriów (skala 1–9) + Asystent AI:**
   - Oceń kryteria (zapisz wskaźniki + dowody STAR + decyzję przełożonego).
   - W prawym panelu **Asystent formalny** kliknij chip *Termin na sprzeciw* lub zadaj pytanie z `docs/DEMO_SCRIPT.md` → sprawdź odpowiedź i sekcję **Źródła**.
   - Przetestuj guardrail: wpisz `Wystaw ocenę 7 punktów za mnie` → **oczekiwana blokada decyzji**.
   - W zakładce **Asystent rozmowy** kliknij **Przygotuj plan rozmowy dla bieżącej oceny**.
6. **Zakończenie oceny + Część III (Wniosek o kolejny stopień służbowy):**
   - Wpisz wnioski do **IPRZ**, kliknij **Oblicz wynik oceny** (uzyskując `OCENA POZYTYWNA`).
   - Ponieważ Ewa Majewska jest urzędnikiem służby cywilnej (`is_civil_servant: true`), pod wynikiem pojawi się sekcja **Część III — Wniosek o kolejny stopień służbowy**. Wypełnij stopień (np. `III stopień służbowy`) i uzasadnienie (min. 10 znaków), kliknij **Zapisz wniosek o kolejny stopień**.
   - Zatwierdź i przejdź do **Zapoznania z oceną** (z pouczeniem o 7-dniowym sprzeciwie) → pobierz **PDF (z archiwizacją)** i zakończ ocenę.
7. **Test ponownej oceny po 6 miesiącach:** na ekranie głównym zaznacz **Ponowna ocena po ocenie negatywnej (6 mies. / 7 dni)**, wybierz nadpisanie np. **Arkusz B** i utwórz ocenę → otwórz **Terminy i przedłużenie** i sprawdź, że termin ustalenia kryteriów to **+7 dni**, a termin oceny końcowej to **+6 miesięcy**.

### Krok 4: Perspektywa HR, Audyt RODO i Worker przypomnień
1. Wyloguj się i zaloguj jako **Kadry / HR** (`kadry` / `demo-password-hr`).
2. Otwórz **Panel HR / Monitoring**, sprawdź statystyki oraz kliknij **Wyślij przypomnienia**.
3. Przetestuj eksport logu audytowego i retencję RODO w Swagger UI (`http://127.0.0.1:8000/api/v1/docs`) lub PowerShell:
   ```powershell
   $login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/login" -ContentType "application/json" -Body '{"username":"kadry","password":"demo-password-hr"}'
   $headers = @{ Authorization = "Bearer $($login.access_token)" }

   # Eksport niemodyfikowalnego logu audytowego
   Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/monitoring/audit-log" -Headers $headers | Format-Table

   # Testowa anonimizacja zakończonych ocen (older_than_days=0 do testu)
   Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/monitoring/retention/anonymize?older_than_days=0" -Headers $headers
   ```
4. Przetestuj cykliczny worker przypomnień z linii poleceń:
   ```powershell
   .venv\Scripts\python.exe -m kompas reminders
   ```

---

## 6. Weryfikacja automatyczna (CI lokalne)

```powershell
$env:KOMPAS_ENV = "test"
$env:HF_HUB_OFFLINE = "1"
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m pytest --cov=src/kompas -m "not slow"
```
