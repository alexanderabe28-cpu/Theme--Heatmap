"""Breadth-Scanner: taegliche Datenerfassung (GitHub Actions) fuer die Theme-Heatmap.

Module:
    universe  – Konstituentenlisten S&P 500 / Nasdaq Composite / Russell 2000
    prices    – OHLCV-Download von Yahoo in Bloecken (mit Retries)
    metrics   – Indikatoren + Breadth-Zeitreihen (vektorisiert ueber alle Titel)
    scan      – eigener Scanner (ATR%-Multiple vom MA50, RVOL, Trend, ...)
    run_daily – Einstiegspunkt: python -m scanner.run_daily
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
UNIVERSE_DIR = os.path.join(DATA_DIR, "universe")
SCAN_DIR = os.path.join(DATA_DIR, "scan")
CONFIG_FILE = os.path.join(ROOT, "scanner_config.json")
