# Piano di Implementazione: AI Bank Statement Categorizer - Progetto Wheresmymoney

---

## 1. Contesto del Progetto

L'obiettivo è sviluppare un'applicazione Python che automatizzi l'inserimento e la categorizzazione delle spese bancarie all'interno di un Google Sheet preesistente.
Il sistema riceve in input estratti conto in formato CSV/Excel provenienti da diverse banche (con tracciati record differenti), estrae le transazioni, utilizza un LLM (es. API di Google Gemini) per assegnare una categoria a ciascuna spesa basandosi su un elenco di categorie predefinite, e infine appende i dati elaborati nelle rispettive schede del Google Sheet.

**Vincoli architetturali cruciali:**

- Il Google Sheet di destinazione ha una struttura mista: le prime righe (es. 0-12) contengono tabelle di riepilogo e formule. Le transazioni iniziano più in basso.
- L'applicazione **non deve mai sovrascrivere o modificare i dati esistenti o le formule**. Deve esclusivamente effettuare un'operazione di `APPEND` alla fine della lista delle transazioni esistenti per la specifica scheda bancaria.
- L'elenco delle categorie valide deve essere letto dinamicamente dal foglio "Categorie" presente nel Google Sheet.

---

## 2. Piano di Realizzazione a Step Verificabili

### Fase 1: Configurazione Ambiente e Connessioni API

- **Obiettivo:** Creare l'impalcatura del progetto e stabilire le connessioni con i servizi esterni.
- **Azioni:**
  1. Inizializzare un progetto Python con un file `requirements.txt` (pandas, gspread, google-generativeai, python-dotenv).
  2. Configurare l'autenticazione a Google Sheets tramite Service Account.
  3. Configurare il client per l'API dell'LLM (Gemini).
- **Verifica di completamento:** Uno script di test riesce a leggere il nome dei fogli dal Google Sheet target e riceve una risposta di "hello world" dall'API dell'LLM.

### Fase 2: Modulo di Ingestion e Normalizzazione (Data Cleaning)

- **Obiettivo:** Tradurre i vari formati delle banche in un formato standard interno.
- **Azioni:**
  1. Creare una classe o funzioni di parsing specifiche per ogni banca (es. `parse_lisa_csv`, `parse_comune_bpm_csv`, ecc.).
  2. Mappare le colonne eterogenee in un set standard: `Data` (DD/MM/YYYY), `Importo` (Float, attenzione ai separatori di migliaia/decimali e ai segni), `Descrizione Originale`.
  3. Filtrare eventuali righe vuote o righe di intestazione non pertinenti.
- **Verifica di completamento:** Passando un file CSV grezzo di test per ogni banca, il modulo restituisce un `pandas.DataFrame` con le colonne standardizzate e i tipi di dato corretti.

### Fase 3: Integrazione Google Sheets (Lettura Categorie)

- **Obiettivo:** Recuperare le categorie valide dal file master.
- **Azioni:**
  1. Sviluppare una funzione che legga il foglio "Categorie" (o la scheda dedicata) dal Google Sheet.
  2. Estrarre la lista dei nomi delle categorie in un array/lista Python.
- **Verifica di completamento:** La funzione stampa a terminale l'array esatto delle categorie attualmente presenti sul Google Sheet.

### Fase 4: Motore di Categorizzazione (LLM Prompting)

- **Obiettivo:** Assegnare la categoria corretta a ogni transazione e generare una descrizione "pulita".
- **Azioni:**
  1. Scrivere un prompt system/istruzione che fornisca all'LLM il ruolo di analista finanziario, la lista delle categorie valide e le regole di output (es. JSON o testo formattato).
  2. Creare una funzione che iteri sulle transazioni (o le invii in batch per ottimizzare i costi/tempi) e interroghi l'LLM.
  3. Gestire eventuali risposte non valide (fallbacks) assegnando una categoria "Da Verificare".
- **Verifica di completamento:** Passando un DataFrame di 5 transazioni fittizie e la lista di categorie, la funzione restituisce le transazioni con due nuove colonne: `Categoria Assegnata` e `Descrizione Pulita`.

### Fase 5: Modulo di Scrittura (Append su Google Sheets)

- **Obiettivo:** Inserire i dati elaborati nel foglio corretto in modo sicuro.
- **Azioni:**
  1. Determinare dinamicamente la prima riga vuota disponibile nella sezione "transazioni" della scheda bersaglio (saltando l'intestazione e i riepiloghi iniziali).
  2. Mappare il DataFrame standardizzato nell'ordine esatto delle colonne richieste da quella specifica scheda (es. `Mese, Data Valuta, Addebiti, Divisa, Cat, Descrizione`).
  3. Eseguire la chiamata API di `append_rows` tramite `gspread`.
- **Verifica di completamento:** Eseguendo lo script, 3 righe di test vengono aggiunte in fondo alla scheda "Comune_bpm" senza alterare le formule in alto.

### Fase 6: Interfaccia Utente (Opzionale ma raccomandata)

- **Obiettivo:** Rendere l'app usabile dall'utente finale senza toccare il codice.
- **Azioni:**
  1. Creare una semplice interfaccia web con `Streamlit`.
  2. Aggiungere un menu a tendina per selezionare la banca/scheda di destinazione.
  3. Aggiungere un widget per l'upload del file CSV.
  4. Mostrare un'anteprima della categorizzazione fatta dall'LLM prima di confermare la scrittura sul Google Sheet.
- **Verifica di completamento:** L'utente può caricare un file, vedere la tabella con le categorie indovinate, modificare eventualmente una categoria sbagliata, e cliccare "Salva su Sheets".

---

## 3. Lista degli Input Necessari (A carico dell'utente)

Dati sensibili come chiavi api vanno inserite in file `.env` o in un sistema di gestione segreti.
Dati di esempio e file di test vanno forniti in una cartella `test_data/` all'interno del progetto.

**1. Credenziali e Accessi:**

- **Google Cloud Service Account JSON:** Un file `.json` contenente le credenziali di un account di servizio Google (necessario per far leggere/scrivere l'app sul tuo Google Sheet senza login manuale).
- **ID del Google Sheet:** La stringa alfanumerica presente nell'URL del tuo foglio Google (es. `https://docs.google.com/spreadsheets/d/`**QUESTO_E_L_ID**`/edit`). _Ricordati di condividere il foglio con l'email del Service Account dandogli i permessi di "Editor"._
- **API Key per l'LLM:** Una chiave API valida per Google Gemini (ottenibile da Google AI Studio) o per OpenAI, a seconda di quale motore decidi di usare.

**2. Dati di Esempio (Test Data):**

- **File Grezzi delle Banche:** Un file `.csv` o `.xlsx` di esempio per _ogni singola banca_ che intendi supportare (es. un file originale intatto della banca di Lisa, uno del Comune, uno della Carta di Credito). I file che mi hai già mostrato vanno bene, ma l'agente di coding avrà bisogno dei file _originali grezzi scaricati dalla banca_, non quelli già formattati nel Google Sheet.
- **Regole di Mappatura Fisse (Opzionale):** Se ci sono spese che non vuoi far passare per l'LLM per risparmiare tempo/token (es. "Se la descrizione contiene 'MUTUO', la categoria è sicuramente 'Mutuo'"), fornisci una breve lista di queste regole.

**3. Struttura del Foglio Master:**

- **Elenco esatto delle colonne per ogni scheda:** L'agente di coding ha bisogno di sapere esattamente l'ordine delle colonne in cui andranno incollati i dati. Per esempio, per il conto Lisa l'ordine sembra essere: `Mese | Data Valuta | Addebiti | Divisa | Cat | Descrizione`. Questo deve essere precisato per ogni tab del file master.

---

## Plan: Wheresmymoney MVP Checklist

Checklist operativa per implementare il MVP come pipeline CLI interattiva append-only verso Google Sheets.

**Checklist**

1. Bloccare la specifica del foglio target

- [x] Confermare `spreadsheet_id` unico
- [x] Confermare nome del foglio `Categorie`
- [x] Elencare i tab bancari consentiti
- [x] Elencare i due tab di analisi vietati
- [x] Confermare la riga iniziale fissa delle transazioni
- [x] Confermare l’ordine esatto delle colonne da scrivere nei tab bancari
- [x] Decidere dove configurare eventuali regole deterministiche iniziali

2. Preparare il bootstrap del progetto

- [x] Creare la struttura base del progetto Python
- [x] Definire le dipendenze minime (`pandas`, `gspread`, provider Gemini, `python-dotenv`, `openpyxl`, `pytest`)
- [x] Preparare il caricamento della configurazione da `.env`
- [x] Preparare la configurazione per Google Sheets
- [x] Preparare la configurazione per il provider LLM
- [x] Aggiungere uno smoke test di connessione ai servizi esterni

3. Definire il modello dati canonico

- [x] Formalizzare i campi del modello transazione (`source_bank`, `transaction_date`, `value_date`, `amount`, `currency`, `original_description`, `cleaned_description`, `assigned_category`)
- [x] Definire la normalizzazione degli importi in un solo valore signed
- [x] Definire quando usare `transaction_date` e quando `value_date`
- [x] Escludere esplicitamente `Mese` dal payload di scrittura
- [x] Definire eventuali campi tecnici opzionali per logging o debug

4. Implementare i parser per banca

- [ ] Raccogliere almeno un file grezzo anonimizzato per ogni banca supportata
- [ ] Implementare un parser isolato per ogni formato banca
- [ ] Gestire file CSV e XLSX dove necessario
- [ ] Gestire banche con una colonna importo signed
- [ ] Gestire banche con due colonne separate dare/avere
- [ ] Scartare righe vuote, intestazioni duplicate e footer non pertinenti
- [ ] Verificare che vengano importati tutti i movimenti

5. Integrare le categorie dal Google Sheet

- [ ] Leggere dinamicamente le categorie dal foglio `Categorie`
- [ ] Validare che le categorie lette siano categorie foglia finali
- [ ] Decidere la policy su eventuali categorie vuote o duplicate
- [ ] Definire il fallback tecnico `Da Verificare`

6. Aggiungere regole deterministiche prima dell’LLM

- [ ] Definire un formato configurabile per le regole di matching
- [ ] Implementare il matching su descrizione o pattern ricorrenti
- [ ] Applicare le regole prima di chiamare il classificatore LLM
- [ ] Tracciare quali transazioni sono state classificate da regole e quali da LLM

7. Implementare il classificatore LLM

- [ ] Definire un prompt con istruzioni rigide e output JSON
- [ ] Passare al modello solo le transazioni non risolte dalle regole
- [ ] Validare localmente il JSON restituito
- [ ] Verificare che la categoria restituita appartenga alla lista valida
- [ ] In caso di errore o categoria fuori lista assegnare `Da Verificare`
- [ ] Conservare una `cleaned_description` sicura anche nei fallback

8. Costruire la CLI interattiva di revisione

- [ ] Mostrare all’utente tutte le transazioni normalizzate e categorizzate
- [ ] Per ogni transazione mostrare almeno data, importo, descrizione originale, descrizione pulita e categoria proposta
- [ ] Permettere all’utente di accettare la categoria suggerita
- [ ] Permettere all’utente di cambiarla scegliendo dalla lista completa delle categorie valide
- [ ] Chiedere conferma finale prima della scrittura
- [ ] Consentire annullamento completo senza side effect

9. Implementare il writer append-only verso Google Sheets

- [ ] Consentire scrittura solo nei tab bancari autorizzati
- [ ] Bloccare qualunque tentativo di scrittura nei tab di analisi
- [ ] Usare la riga iniziale fissa delle transazioni come vincolo di sicurezza
- [ ] Mappare il modello canonico nell’ordine colonne del foglio
- [ ] Non scrivere la colonna `Mese`
- [ ] Appendere solo nuove righe senza aggiornare celle esistenti
- [ ] Verificare che formule e storico restino intatti

10. Aggiungere logging ed error handling

- [ ] Loggare parsing, classificazione, revisione e append
- [ ] Gestire errori di lettura file
- [ ] Gestire errori Google Sheets
- [ ] Gestire errori LLM con retry ragionati dove opportuno
- [ ] Restituire messaggi chiari in CLI in caso di fallimento

11. Coprire il flusso con test

- [ ] Scrivere test unitari per i parser
- [ ] Scrivere test unitari per la lettura e validazione categorie
- [ ] Scrivere test unitari per il mapping verso Sheets
- [ ] Scrivere test unitari per i fallback del classificatore LLM
- [ ] Scrivere test funzionali per la CLI interattiva
- [ ] Preparare uno sheet di staging per i test di integrazione
- [ ] Scrivere un test end-to-end da file grezzo a revisione CLI a append

12. Definire il criterio di done del MVP

- [ ] Un file grezzo bancario può essere importato correttamente
- [ ] Le transazioni vengono normalizzate nel modello unico
- [ ] Le categorie valide vengono lette dal foglio
- [ ] La categorizzazione combina regole e LLM con fallback sicuro
- [ ] L’utente può correggere ogni categoria da terminale
- [ ] L’utente può confermare o annullare prima della scrittura
- [ ] L’append scrive solo nel tab bancario corretto
- [ ] Nessuna formula o dato esistente viene modificato
- [ ] I tab di analisi non vengono mai toccati

**Out of scope del MVP**

- [ ] Deduplica automatica dei movimenti
- [ ] UI web Streamlit nel primo rilascio
- [ ] Supporto a più Google Sheet
