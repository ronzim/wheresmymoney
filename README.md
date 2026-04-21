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
