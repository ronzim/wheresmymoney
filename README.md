# Wheresmymoney

## Punto 3 implementato

Il modello dati canonico delle transazioni e' ora definito in codice, con
validazione esplicita su date, importi, valuta e payload verso Google Sheets.

File introdotti:

- `src/wheresmymoney/models.py`: modello `Transaction` e helper di normalizzazione.
- `tests/test_models.py`: test unitari sul modello canonico.

Regole fissate nel modello:

- `transaction_date` e `value_date` accettano `dd/mm/yyyy` o `yyyy-mm-dd`
- `amount` viene normalizzato in un unico valore signed con due decimali
- `currency` viene normalizzata come codice ISO a 3 lettere
- `cleaned_description` e `assigned_category` sono opzionali
- la descrizione esportata verso Google Sheets e' sempre quella originale del file banca, senza modifiche o riassunti
- `Mese` non puo' comparire nel payload di scrittura verso Sheets

## Punto 4 avviato

La base parser ora supporta due famiglie di export bancario verificate sui file
campione presenti in `test-data`.

File introdotti:

- `src/wheresmymoney/parsers.py`: autodetect formato e parsing in `Transaction`
- `tests/test_parsers.py`: test sui file campione reali

Formati coperti:

- `.xlsx` con header strutturato `Data Op.`, `Data Val.`, `Descrizione`, `Importo`, `Div.`
- `.xlsx` con colonne separate `Addebiti (euro)` e `Accrediti (euro)` da convertire in importo signed
- `.xls` che in realta' contiene una tabella HTML con `Data Contabile`, `Data Valuta`, `Importo`, `Divisa`, `Causale / Descrizione`

## Punto 5 implementato

La lettura delle categorie dal Google Sheet e' ora codificata nel servizio dedicato.

File introdotti:

- `src/wheresmymoney/categories.py`: lettura e validazione del catalogo categorie
- `tests/test_categories.py`: test unitari sulla policy delle categorie

Policy adottata:

- si legge solo la prima colonna del foglio `Categorie`
- si ignora l'intestazione `Categorie`
- si ignorano righe vuote
- si trimmano i nomi categoria ai bordi
- i duplicati fanno fallire il caricamento

Comando utile:

```bash
uv run wheresmymoney-list-categories
```

## Punto 6 implementato

Il layer di regole deterministiche prima dell'LLM e' ora disponibile e validato.

File introdotti:

- `src/wheresmymoney/deterministic_rules.py`: caricamento e applicazione delle regole
- `tests/test_deterministic_rules.py`: test unitari sul motore regole

Comportamento:

- le regole vengono lette da JSON
- ogni regola usa oggi il criterio `contains`
- la categoria di ogni regola viene validata contro il catalogo reale categorie
- il primo match vince
- i match vengono tracciati con `classification_source = "rule"`
- le transazioni non matchate restano separate e possono passare all'LLM

## Punto 7 implementato

Il classificatore LLM con output strutturato e fallback locale e' ora disponibile.

File introdotti:

- `src/wheresmymoney/llm_categorizer.py`: prompt, chiamata al modello, parsing JSON e fallback
- `tests/test_llm_categorizer.py`: test unitari del classificatore

Comportamento:

- il prompt richiede JSON puro con `assigned_category` e `cleaned_description`
- si passano al modello solo le transazioni gia' rimaste fuori dalle regole deterministiche
- la risposta viene validata localmente con parser JSON esplicito
- la categoria viene validata contro il catalogo categorie
- in caso di JSON invalido o categoria fuori lista si usa `Da Verificare`
- in fallback `cleaned_description` resta una versione sicura della descrizione originale

## Punto 8 implementato

La CLI interattiva di revisione e' ora disponibile come modulo applicativo testabile.

File introdotti:

- `src/wheresmymoney/review_cli.py`: revisione interattiva riga per riga
- `tests/test_review_cli.py`: test della CLI con input simulato

Comportamento:

- mostra data, importo, descrizione originale, descrizione pulita e categoria proposta
- permette di tenere la categoria corrente con Invio
- permette di cambiare categoria scegliendo un indice dalla lista completa
- mostra un riepilogo finale di tutte le transazioni prima della conferma
- permette di riaprire una transazione dal riepilogo finale digitandone l'indice
- chiede conferma finale prima della scrittura
- permette annullamento completo senza side effect

## Punto 9 implementato

Il writer append-only verso Google Sheets e' ora implementato con mapping sicuro.

File introdotti:

- `src/wheresmymoney/sheet_writer.py`: writer append-only e integrazione gspread
- `tests/test_sheet_writer.py`: test unitari su next row, mapping e range di scrittura

Comportamento:

- verifica che il tab sia tra quelli bancari autorizzati
- legge l'header reale del foglio per decidere il mapping di scrittura
- se il tab include `Mese`, scrive una formula `=MONTH(Bn)` nelle nuove righe
- scrive solo righe nuove senza toccare quelle esistenti
- usa il payload dominio senza includere `Mese` come dato sorgente

## Punto 10 implementato

La pipeline CLI end-to-end ora espone un comando unico con logging ed error handling.

File introdotti:

- `src/wheresmymoney/cli_import.py`: orchestration parse -> categorie -> regole -> LLM -> review -> append
- `tests/test_cli_import.py`: test end-to-end locale con retry LLM e append simulato

Comportamento:

- aggiunge il comando `uv run wheresmymoney-import`
- logga parse, caricamento categorie, regole, LLM, review e append
- gestisce errori parser, config, Google Sheets e writer con messaggi CLI chiari
- applica retry ragionato alla sola fase LLM in caso di errore esterno
- supporta `--dry-run` per verificare il flusso senza scrittura

Esempio d'uso:

```bash
uv run wheresmymoney-import test-data/ListaMovimenti.xlsx --bank Comune_bpm --dry-run
```

## Punto 11 completato

La copertura test ora include anche un'integrazione live controllata su Google Sheets.

File introdotti:

- `tests/test_google_sheet_integration.py`: append reale su foglio di test con verifica post-scrittura

Comportamento:

- il test live e' gated da `WHERESMYMONEY_RUN_LIVE_TESTS=1`
- usa la pipeline reale fino all'append su un tab bancario autorizzato
- verifica formula `Mese`, data, importo, categoria e descrizione scritta
- non tocca i tab di analisi

Esempio d'uso:

```bash
WHERESMYMONEY_RUN_LIVE_TESTS=1 uv run pytest tests/test_google_sheet_integration.py
```

## Punto 2 implementato

Il bootstrap minimo del progetto Python ora include dipendenze, loader della
configurazione runtime e smoke test CLI.

File introdotti:

- `pyproject.toml`: metadati progetto e dipendenze gestite con `uv`.
- `.gitignore`: esclusione di `.venv`, `.env` e cache locali.
- `.env.example`: variabili ambiente richieste.
- `src/wheresmymoney/__init__.py`: inizializzazione package.
- `src/wheresmymoney/runtime_config.py`: loader e validazione della runtime config.
- `scripts/smoke_test.py`: smoke test per config locale, Google Sheets e Gemini.

Note aggiornate:

- l'integrazione Gemini usa `google.genai`, non piu' `google-generativeai`
- il modello verificato in questo progetto e' `gemini-2.5-flash`

Esempio d'uso:

```bash
uv venv
source .venv/bin/activate
uv sync
cp .env.example .env
uv run wheresmymoney-validate-config config/target_sheet.example.json --tab Comune_bpm
uv run wheresmymoney-smoke-test --config-only
uv run wheresmymoney-smoke-test
```

Compatibilita' temporanea:

- restano disponibili anche `python3 scripts/validate_target_config.py` e
  `python3 scripts/smoke_test.py`, ma i comandi consigliati diventano quelli via
  `uv run`.

Configurazione variabili ambiente:

1. `GOOGLE_SERVICE_ACCOUNT_JSON`
   Inserisci il path locale del file JSON del Service Account Google.
   Esempio: `/home/ronzim/secrets/wheresmymoney-service-account.json`

2. `GEMINI_API_KEY`
   Inserisci la chiave API ottenuta da Google AI Studio.

3. `TARGET_SHEET_CONFIG`
   Punta al file JSON della configurazione foglio. Nel tuo caso attuale puo'
   restare `config/target_sheet.example.json` finche' non vuoi rinominarlo.

4. `GEMINI_MODEL`
   Usa `gemini-2.5-flash`, che e' stato verificato con lo smoke test reale.

Esempio di `.env` reale:

```dotenv
GOOGLE_SERVICE_ACCOUNT_JSON=/home/ronzim/secrets/wheresmymoney-service-account.json
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
TARGET_SHEET_CONFIG=config/target_sheet.example.json
GEMINI_MODEL=gemini-2.5-flash
```

Nota pratica:

- `uv` e' gia' stato installato e validato in questo ambiente.

## Punto 1 implementato

Il primo punto della checklist e' stato materializzato con una configurazione
centralizzata del foglio target e un validator locale.

File introdotti:

- `config/target_sheet.example.json`: template della configurazione da completare.
- `src/wheresmymoney/target_config.py`: modello e validazione dei vincoli.
- `scripts/validate_target_config.py`: controllo da terminale della configurazione.

Nota:

- `protected_analysis_tabs` rappresenta di fatto tutti i tab non scrivibili dal processo.
- In questo insieme possono rientrare sia tab di analisi sia tab di supporto come `Categorie`.

Esempio d'uso:

```bash
python scripts/validate_target_config.py
python scripts/validate_target_config.py --tab comune_bpm
```

Vincoli validati:

- il foglio categorie non puo' coincidere con un tab bancario
- un tab non puo' essere insieme consentito e protetto
- i tab protetti non sono scrivibili
- il tab scelto deve essere presente tra i tab bancari consentiti
- la riga iniziale delle transazioni deve essere positiva
- l'ordine delle colonne del tab bancario deve essere esplicito
