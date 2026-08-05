# Wheresmymoney - comandi di ingestion estratti conto ==>
# Uso: just <recipe> [args]
# Tutti i comandi girano tramite `uv run` nell'ambiente del progetto.

set shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    @just --list

# Esegue la suite di test locale
test:
    uv run pytest

# Valida la configurazione del foglio target per un tab bancario
# Uso: just validate-config tab=Comune_ca
validate-config tab="Comune_bpm":
    uv run wheresmymoney-validate-config config/target_sheet.example.json --tab {{tab}}

# Verifica il solo accesso a config, Google Sheets e Gemini
smoke-config:
    uv run wheresmymoney-smoke-test --config-only

# Verifica completa con accesso reale a Google Sheets e Gemini
smoke:
    uv run wheresmymoney-smoke-test

# Stampa le categorie lette dal foglio Categorie
categories:
    uv run wheresmymoney-list-categories

# Generic: parse + categorizzazione + review SENZA scrittura
# Uso: just dry-import <file> <bank>
dry-import file bank:
    uv run wheresmymoney-import "{{file}}" --bank "{{bank}}" --dry-run

# Generic: pipeline completa CON append su Google Sheets
# Uso: just import <file> <bank>
import file bank:
    uv run wheresmymoney-import "{{file}}" --bank "{{bank}}"

# Convenience - conto Mattia
dry-mattia file="real-data/movimentiContoMattia.xlsx":
    @just --justfile {{justfile()}} dry-import "{{file}}" Mattia

# Convenience - conto Mattia (scrittura reale)
mattia file="real-data/movimentiContoMattia.xlsx":
    @just --justfile {{justfile()}} import "{{file}}" Mattia

# Convenience - conto Lisa
dry-lisa file="real-data/ListaMovimentiLisa.xlsx":
    @just --justfile {{justfile()}} dry-import "{{file}}" Lisa

# Convenience - conto Lisa (scrittura reale)
lisa file="real-data/ListaMovimentiLisa.xlsx":
    @just --justfile {{justfile()}} import "{{file}}" Lisa

# Convenience - conto Comune BPM
dry-bpm file="real-data/movimentiContoComuneBPM.xlsx":
    @just --justfile {{justfile()}} dry-import "{{file}}" Comune_bpm

# Convenience - conto Comune BPM (scrittura reale)
bpm file="real-data/movimentiContoComuneBPM.xlsx":
    @just --justfile {{justfile()}} import "{{file}}" Comune_bpm

# Convenience - conto Comune CAI (sovrascrivi `file` se cambia nome/timestamp)
dry-cai file="real-data/Lista Movimenti_CAI_20260805155317.xlsx":
    @just --justfile {{justfile()}} dry-import "{{file}}" Comune_ca

# Convenience - conto Comune CAI (scrittura reale)
cai file="real-data/Lista Movimenti_CAI_20260805155317.xlsx":
    @just --justfile {{justfile()}} import "{{file}}" Comune_ca