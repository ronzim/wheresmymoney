# Wheresmymoney

Tool CLI per importare estratti conto bancari, categorizzarli con regole + LLM, farli rivedere manualmente e appenderli in modo append-only su Google Sheets.

## Utilizzo

### Obiettivo del tool

Il flusso operativo e' questo:

1. leggere un file bancario grezzo
2. normalizzare i movimenti in un modello unico
3. caricare le categorie valide dal Google Sheet
4. applicare regole deterministiche
5. classificare il resto con Gemini
6. far revisionare tutto da terminale
7. appendere solo nuove righe nel tab bancario corretto

Il tool non modifica righe esistenti e non scrive mai nei tab di analisi.

### Quick start

Dopo aver configurato l'ambiente:

```bash
uv run wheresmymoney-import test-data/ListaMovimenti.xlsx --bank Comune_bpm --dry-run
```

Questo comando esegue l'intera pipeline senza scrivere sul foglio.

Per una scrittura reale, basta togliere `--dry-run`:

```bash
uv run wheresmymoney-import test-data/ListaMovimenti.xlsx --bank Comune_bpm
```

### Comando principale

```bash
uv run wheresmymoney-import <file_path> --bank <tab_bancario> [--dry-run] [--llm-attempts N]
```

Parametri principali:

- `file_path`: file bancario da importare
- `--bank`: nome del tab bancario di destinazione, che identifica anche la sorgente logica
- `--dry-run`: esegue parse, categorizzazione e review senza append finale
- `--llm-attempts`: numero massimo di retry per singola transazione in caso di errore esterno LLM

### Esempi pratici

Validare solo la configurazione del foglio:

```bash
uv run wheresmymoney-validate-config config/target_sheet.example.json --tab Comune_bpm
```

Verificare accesso a config, Google Sheets e Gemini:

```bash
uv run wheresmymoney-smoke-test --config-only
uv run wheresmymoney-smoke-test
```

Stampare le categorie lette dal foglio:

```bash
uv run wheresmymoney-list-categories
```

Import reale con review interattiva:

```bash
uv run wheresmymoney-import test-data/movimentiConto-1.xls --bank Comune_bpm
```

### Review CLI

Durante la review il tool:

- mostra ogni transazione con data, importo, descrizione originale, descrizione pulita e categoria proposta
- usa una selezione interattiva nel terminale con frecce e invio quando l'ambiente e' TTY compatibile
- permette di tenere la categoria corrente o sostituirla scegliendola da una lista navigabile
- permette di azzerare la categoria manualmente con il tasto `0` (nessuna categoria)
- mostra un riepilogo finale completo prima della conferma
- permette di riaprire una transazione dal riepilogo finale scegliendola da un menu finale
- permette di confermare o annullare l'append finale

Se il terminale non supporta la UI interattiva oppure la libreria non e' disponibile, il tool mantiene automaticamente il fallback testuale gia' esistente.

### Garanzie operative

- la descrizione scritta su Google Sheets e' sempre quella originale del file banca
- la colonna `Mese` non viene presa dai dati sorgente
- se il tab usa `Mese` come formula in colonna A, il writer scrive `=MONTH(Bn)` nelle nuove righe
- i tab protetti come `Categorie` e `Andamento` non sono scrivibili
- le transazioni non coperte da regole vengono inviate a Gemini in batch, per ridurre numero di chiamate, latenza e costo
- in caso di errore LLM persistente, la transazione degrada in modo sicuro a `Da Verificare`
- dopo la classificazione automatica e dopo ogni transazione revisionata, il tool salva un checkpoint locale per poter riprendere la review senza rifare parse, regole e chiamate LLM
- il checkpoint locale viene eliminato solo dopo un append riuscito su Google Sheets

### Formati bancari attualmente coperti

- `.xlsx` con header strutturato `Data Op.`, `Data Val.`, `Descrizione`, `Importo`, `Div.`
- `.xlsx` con colonne separate `Addebiti (euro)` e `Accrediti (euro)`
- `.xls` che contiene una tabella HTML con `Data Contabile`, `Data Valuta`, `Importo`, `Divisa`, `Causale / Descrizione`

## Ambiente Di Sviluppo

### Requisiti

- Python 3.10+
- `uv`
- un file JSON di Service Account Google condiviso come Editor sul foglio target
- una Gemini API key valida

### Setup iniziale

```bash
uv venv
source .venv/bin/activate # (linux)
.venv\Scripts\activate # (windows)
uv sync
cp .env.example .env
```

### Variabili ambiente

Il file `.env.example` contiene:

```dotenv
GOOGLE_SERVICE_ACCOUNT_JSON=/absolute/path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key
TARGET_SHEET_CONFIG=config/target_sheet.example.json
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BATCH_SIZE=20
WHERESMYMONEY_CHECKPOINT_DIR=.wheresmymoney-checkpoints
```

Significato:

1. `GOOGLE_SERVICE_ACCOUNT_JSON`
   Path locale al file JSON del Service Account Google.

2. `GEMINI_API_KEY`
   API key Gemini generata da Google AI Studio.

3. `TARGET_SHEET_CONFIG`
   Path alla configurazione JSON del foglio target.

4. `GEMINI_MODEL`
   Modello Gemini usato dalla pipeline. Quello verificato in questo progetto e' `gemini-2.5-flash`.

5. `GEMINI_BATCH_SIZE`
   Numero di transazioni inviate a Gemini per singola chiamata. Deve essere un intero positivo. Se non lo imposti, il default e' `20`.

6. `WHERESMYMONEY_CHECKPOINT_DIR`
   Directory locale dove il tool salva i checkpoint della review per poter riprendere senza rifare la classificazione. Se non la imposti, il default e' `.wheresmymoney-checkpoints`.

Per impostarle, aggiungi o modifica queste righe nel file `.env`:

```dotenv
GEMINI_BATCH_SIZE=20
WHERESMYMONEY_CHECKPOINT_DIR=.wheresmymoney-checkpoints
```

Valori piu' alti di `GEMINI_BATCH_SIZE` riducono il numero di chiamate ma aumentano la dimensione del prompt. Valori piu' bassi riducono il payload per richiesta ma aumentano il numero di chiamate.

Se interrompi il processo durante la review, al prossimo avvio dello stesso import il tool riparte automaticamente dall'ultima transazione gia' revisionata trovando il checkpoint in questa directory.

### Configurazione del foglio target

La configurazione principale vive in `config/target_sheet.example.json` e definisce:

- `spreadsheet_id`
- `categories_sheet_name`
- `allowed_bank_tabs`
- `protected_analysis_tabs`
- `transaction_start_row`
- `bank_tab_columns`
- `deterministic_rules_path`

Vincoli validati:

- il foglio categorie non puo' coincidere con un tab bancario
- un tab non puo' essere insieme consentito e protetto
- i tab protetti non sono scrivibili
- il tab scelto deve comparire tra i tab bancari autorizzati
- la riga iniziale delle transazioni deve essere positiva
- l'ordine colonne di output deve essere esplicito

### Configurazione delle regole deterministiche

Le regole deterministiche sono configurate tramite il campo `deterministic_rules_path` dentro `config/target_sheet.example.json`.

Il file di esempio attuale e' `config/deterministic_rules.example.json`.

Formato supportato:

```json
{
  "rules": [
    {
      "contains": "MUTUO",
      "category": "Mutuo"
    },
    {
      "contains": "SUPERMERCATO",
      "category": "Spesa"
    }
  ]
}
```

Significato dei campi:

1. `rules`
   Lista ordinata di regole.

2. `contains`
   Sottostringa cercata nella `original_description` della transazione.

3. `category`
   Categoria da assegnare se la regola matcha.

Comportamento del motore:

- il match e' case-insensitive
- il primo match vince
- se nessuna regola matcha, la transazione passa al classificatore LLM
- la categoria deve esistere nel catalogo reale letto dal foglio `Categorie`
- condizioni duplicate fanno fallire il caricamento della configurazione

Indicazioni pratiche:

- usa regole solo per pattern molto stabili e ricorrenti
- preferisci descrizioni abbastanza specifiche da evitare falsi positivi
- tieni le regole piu' specifiche prima di quelle piu' generiche
- dopo ogni modifica, verifica il comportamento con un import in `--dry-run`

### Dipendenze principali

Il progetto usa:

- `gspread`
- `google-genai`
- `openpyxl`
- `pandas`
- `python-dotenv`
- `pytest`

### Test

Test unitari principali:

```bash
uv run pytest
```

Test live di integrazione Google Sheets:

```bash
WHERESMYMONEY_RUN_LIVE_TESTS=1 uv run pytest tests/test_google_sheet_integration.py
```

Questo test fa un append reale sul foglio di test e verifica subito dopo la riga scritta.

### Note per lo sviluppo

- i comandi consigliati sono quelli via `uv run`
- restano disponibili anche alcuni wrapper in `scripts/`, ma sono solo compatibilita' temporanea
- il progetto e' pensato per essere usato prima in `--dry-run`, poi in append reale

## Recap Implementazione

### Punto 1

Configurazione centralizzata del foglio target e validator locale.

File principali:

- `config/target_sheet.example.json`
- `src/wheresmymoney/target_config.py`
- `scripts/validate_target_config.py`

### Punto 2

Bootstrap del progetto Python, configurazione runtime e smoke test.

File principali:

- `pyproject.toml`
- `.env.example`
- `src/wheresmymoney/runtime_config.py`
- `src/wheresmymoney/cli_smoke_test.py`

### Punto 3

Modello dati canonico `Transaction` con validazione di date, importi, valuta e export verso Sheets.

File principali:

- `src/wheresmymoney/models.py`
- `tests/test_models.py`

### Punto 4

Parser per i formati bancari reali attualmente supportati.

File principali:

- `src/wheresmymoney/parsers.py`
- `tests/test_parsers.py`

### Punto 5

Lettura e validazione dinamica delle categorie dal foglio `Categorie`.

File principali:

- `src/wheresmymoney/categories.py`
- `tests/test_categories.py`

### Punto 6

Layer di regole deterministiche prima dell'LLM.

File principali:

- `src/wheresmymoney/deterministic_rules.py`
- `tests/test_deterministic_rules.py`

### Punto 7

Classificatore LLM con output JSON strutturato, batching delle richieste e fallback locale sicuro.

File principali:

- `src/wheresmymoney/llm_categorizer.py`
- `tests/test_llm_categorizer.py`

### Punto 8

Review CLI interattiva con riepilogo finale e riapertura per indice.

File principali:

- `src/wheresmymoney/review_cli.py`
- `tests/test_review_cli.py`

### Punto 9

Writer append-only verso Google Sheets con preservazione della logica `Mese`.

File principali:

- `src/wheresmymoney/sheet_writer.py`
- `tests/test_sheet_writer.py`

### Punto 10

Pipeline end-to-end con logging, error handling e comando unico CLI.

File principali:

- `src/wheresmymoney/cli_import.py`
- `tests/test_cli_import.py`

### Punto 11

Copertura test con integrazione live controllata su Google Sheets.

File principali:

- `tests/test_google_sheet_integration.py`

### Stato attuale

Il MVP CLI append-only e' implementato, testato localmente e verificato anche con test live sul foglio Google di prova.
