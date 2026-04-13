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

## 4. Punti ancora da chiarire

- "modello dati interno"
- come gestire il layer di regole fisse da usare prima dell'llm
- approfondire gestione errori
- test
