"""Aktuelle Charts zum Pine-Indikator. Aufruf: python charts_pine.py <datenordner> <zielordner>
Kurs: Index-Kerzen (Yahoo, OHLC). Zustaende, Marker und Risikofenster: Modellwerte aus levels_py.csv,
die im Fenster mit der Ausgabe des Pine-Indikators auf TradingView uebereinstimmen (Abgleich ueber 500 Tage).
Darstellung wie im Indikator: Dreieck ueber dem Kurs, darunter "LEVEL n" mit den Bestaetigungen,
blasses Band = Risikofenster (45 Sessions nach dem letzten Tag im Warnzustand)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerBase
from matplotlib.patches import Patch
from matplotlib.text import Text
from matplotlib.ticker import FuncFormatter

data, dest = Path(sys.argv[1]), Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
N = 260                                            # Sessions im Bild
MIN_MARK = 2                                       # Marker ab Level, wie die Voreinstellung im Pine-Script
RISK_LEN = 45                                      # Risikofenster in Sessions
SURF, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#898781", "#2c2c2a"
C_CALM, C_OFF = "#3987e5", "#5d5f63"
LVL_COL = {1: "#fab219", 2: "#ec835a", 3: "#d03b3b", 4: "#b04fd0"}      # Abstufung wie im Pine-Script
LVL_NAME = {0: "unauffällig", 1: "ELEVATED", 2: "HIGH", 3: "VERY HIGH", 4: "EXTREME"}
C_WARN = LVL_COL[3]
A_WIN, A_BAND = 0.12, 0.30                         # Deckkraft: Risikofenster, Band des Tages darueber
MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

lv = pd.read_csv(data / "levels_py.csv", index_col=0, parse_dates=True)
ix = pd.read_csv(data / "index_ohlc.csv", index_col=0, parse_dates=True)
C_UP, C_DN = "#35b5a6", "#d6d5cf"                  # Kerzen: auf = tuerkis, ab = hell, damit sie nicht mit den Level-Farben kollidieren
b = lambda s: (lv[s] == True)                      # noqa: E712,E731


class MarkKey:
    """Legendeneintrag fuer die Level-Marker."""


class MarkHandler(HandlerBase):
    def create_artists(self, legend, orig, x0, y0, w, h, fontsize, trans):
        return [Text(x0 + w / 2, y0 + h / 2 - 0.5, "▼", ha="center", va="center", color=LVL_COL[3], fontsize=fontsize * 1.05, transform=trans)]


def de(x: float, nd: int = 0) -> str:
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def since_last(mask: pd.Series) -> pd.Series:
    """Sessions seit dem letzten wahren Tag (0 am Tag selbst), NaN davor."""
    pos = pd.Series(np.where(mask.to_numpy(), np.arange(len(mask)), np.nan), index=mask.index).ffill()
    return pd.Series(np.arange(len(mask)), index=mask.index) - pos


def chart(name: str, title: str, price_col: str, gate_col: str, dist_col: str, level_col: str, fname: str) -> None:
    lvl_all = lv[level_col]
    since_all = since_last((lvl_all >= 3).fillna(False))            # auf der ganzen Historie, wie im Indikator
    d = pd.DataFrame({"px": ix[price_col + "_Close"], "o": ix[price_col + "_Open"], "h": ix[price_col + "_High"],
                      "l": ix[price_col + "_Low"], "gate": b(gate_col), "n": lv["n4"], "dist": lv[dist_col], "since": since_all,
                      "C": b("C"), "B": b("B"), "R": b("R"), "V": b("V")}).dropna(subset=["px", "n"]).iloc[-N:]
    x = np.arange(len(d))
    n = d["n"].to_numpy().astype(int)
    g = d["gate"].to_numpy()
    warn, two = g & (n >= 3), g & (n == 2)
    lev = np.where(g, n, 0)                                         # Level des Tages
    win = (d["since"] <= RISK_LEN).to_numpy()
    last = d.iloc[-1]
    # Level-Marker: Level hoeher als an den 20 Sessions davor (Erstsignal, Spec v1.0)
    lvl = lvl_all.dropna()
    mk = lvl[lvl > lvl.shift(1).rolling(20).max()].astype(int)
    mk = mk[(mk >= MIN_MARK) & (mk.index >= d.index[0])]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": GRID,
                         "axes.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED})
    fig = plt.figure(figsize=(7.2, 8.5), dpi=200, facecolor=SURF)
    gs = fig.add_gridspec(2, 1, height_ratios=[3.1, 1.25], hspace=0.07, left=0.035, right=0.885, top=0.785, bottom=0.105)
    ax, lx = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    # Kopf
    state = "kein Level" if not last["gate"] else f"Level {int(last['n'])} {LVL_NAME[int(last['n'])]}"
    fenster = f"Fenster Tag {int(last['since'])} von {RISK_LEN}" if last["since"] <= RISK_LEN else "Fenster zu"
    fig.text(0.035, 0.963, title, color=INK, fontsize=15, fontweight="bold", va="center")
    fig.text(0.035, 0.927, f"{d.index[-1]:%d.%m.%Y}:  {state}  ·  {de(abs(last['dist']) * 100, 1)} % unter Hoch  ·  "
             f"{int(last['n'])} von 4 Bestätigungen  ·  {fenster}", color=INK2, fontsize=10.2, va="center")
    handles = [Patch(facecolor=LVL_COL[1]), Patch(facecolor=LVL_COL[2]), Patch(facecolor=LVL_COL[3]), Patch(facecolor=LVL_COL[4]),
               Patch(facecolor=C_WARN, alpha=0.32), MarkKey(), Patch(facecolor=C_CALM), Patch(facecolor=C_OFF)]
    labels = ["1 ELEVATED", "2 HIGH", "3 VERY HIGH", "4 EXTREME", f"Risikofenster ({RISK_LEN} Sessions)",
              "Level-Marker mit Bestätigungen", "Gate an", "außerhalb Gate, kein Level"]
    leg = fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.028, 0.912), ncol=2, frameon=False,
                     fontsize=9.6, handlelength=1.1, handleheight=0.9, columnspacing=1.6, labelspacing=0.28,
                     handler_map={MarkKey: MarkHandler()})
    for t in leg.get_texts():
        t.set_color(INK2)

    # Kurs: Risikofenster, darueber die Baender des Tages
    for i in np.where(win)[0]:
        ax.axvspan(i - 0.5, i + 0.5, color=C_WARN, alpha=A_WIN, lw=0)
    for i in np.where(lev >= 2)[0]:                                 # Baender ab Level 2, Farbe nach Level
        ax.axvspan(i - 0.5, i + 0.5, color=LVL_COL[int(lev[i])], alpha=A_BAND, lw=0)
    up = (d["px"] >= d["o"]).to_numpy()
    for m, col in ((up, C_UP), (~up, C_DN)):                        # Kerzen: Docht und Koerper
        ax.vlines(x[m], d["l"][m], d["h"][m], color=col, lw=0.7, zorder=3)
        body_lo, body_hi = np.minimum(d["o"][m], d["px"][m]), np.maximum(d["o"][m], d["px"][m])
        ax.bar(x[m], np.maximum(body_hi - body_lo, (d["h"].max() - d["l"].min()) * 0.0012), bottom=body_lo, width=0.68, color=col, lw=0, zorder=4)
    lo, hi = d["l"].min(), d["h"].max()
    ax.set_xlim(-0.5, len(d) - 0.5)
    ax.set_ylim(lo - (hi - lo) * 0.06, hi + (hi - lo) * 0.16)
    PT = fig.dpi / 72.0                                    # Pixel je Punkt
    placed = []                                            # belegte Rechtecke in Pixeln: (x0, x1, y0, y1)
    for t, k in mk.items():
        i = d.index.get_loc(t)
        col = LVL_COL[int(k)]
        comps = "".join(c for c in "CBRV" if d[c].iloc[i])
        text = f"LEVEL {k} · {comps}"
        ha = "left" if i < 16 else "right" if i > len(d) - 16 else "center"
        xp, yp = ax.transData.transform((i, d["l"].iloc[i]))
        w, h = (len(text) * 5.25 + 9) * PT, 13.5 * PT        # Breite und Hoehe des Kaestchens, geschaetzt
        x0 = xp if ha == "left" else xp - w if ha == "right" else xp - w / 2
        lift = 0.0
        while any(x0 < r[1] + 4 and x0 + w > r[0] - 4 and yp - (15 + lift) * PT > r[2] - 3 and yp - (15 + lift) * PT - h < r[3] + 3
                  for r in placed) and lift < 120:
            lift += 4.0                                      # nach unten schieben, bis nichts ueberlappt
        placed.append((x0, x0 + w, yp - (15 + lift) * PT - h, yp - (15 + lift) * PT))
        ax.annotate("▼", (i, d["h"].iloc[i]), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                    color=col, fontsize=11, zorder=7)
        ax.annotate(text, (i, d["l"].iloc[i]), xytext=(0, -(15 + lift)), textcoords="offset points",
                    ha=ha, va="top", color="#ffffff" if k >= 3 else "#1a1a19", fontsize=8.2, fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.3", fc=col, ec=SURF, lw=0.9),
                    arrowprops=dict(arrowstyle="-", color=col, lw=1.2, shrinkA=0, shrinkB=2))
    ih = int(np.argmax(d["px"].to_numpy()))                         # hoechster Schlusskurs, darauf bezieht sich das Gate
    ax.annotate(f"Hoch\n{d.index[ih]:%d.%m.}", (ih, d["h"].iloc[ih]), xytext=(8, 5),
                textcoords="offset points", ha="left", va="bottom", color=INK2, fontsize=10, linespacing=1.25)
    ax.axhline(last["px"], color=MUTED, lw=0.6, ls=(0, (2, 3)), zorder=1)
    ax.annotate(de(last["px"]), (x[-1], last["px"]), xytext=(7, 0), textcoords="offset points", ha="left", va="center",
                color=INK, fontsize=10.5, fontweight="bold", annotation_clip=False, zorder=6,
                bbox=dict(fc=SURF, ec="none", pad=1.6))

    # Leiste: Bestaetigungen, dahinter das Risikofenster
    for i in np.where(win)[0]:
        lx.axvspan(i - 0.5, i + 0.5, color=C_WARN, alpha=0.10, lw=0)
    colors = [C_OFF if not g[i] else LVL_COL.get(int(n[i]), C_CALM) for i in range(len(d))]
    lx.bar(x, n, width=1.0, color=colors, lw=0)
    lx.axhline(3, color=C_WARN, lw=1.0, ls=(0, (4, 3)), alpha=0.85)
    lx.bar(x[g], np.full(g.sum(), 0.28), bottom=-0.62, width=1.0, color=C_CALM, lw=0)
    lx.set_ylim(-0.75, 4.35)
    lx.set_yticks([-0.48, 0, 1, 2, 3, 4])
    lx.set_yticklabels(["Gate", "0", "1", "2", "3", "4"])
    lx.annotate("Warnschwelle", (0, 3), xytext=(3, 4), textcoords="offset points", color=INK2, fontsize=9, va="bottom", zorder=6,
                bbox=dict(fc=SURF, ec="none", pad=1.4, alpha=0.82))
    lx.set_ylabel("Bestätigungen", color=INK2, fontsize=10, labelpad=6)
    lx.yaxis.set_label_position("right")

    # Achsen
    firsts = [i for i in range(len(d)) if i == 0 or d.index[i].month != d.index[i - 1].month]
    firsts = [i for i in firsts if i > 6 or d.index[i].day <= 3]
    labels = [MON[d.index[i].month - 1] + (f" {d.index[i]:%y}" if d.index[i].month == 1 or i == firsts[0] else "") for i in firsts]
    for a in (ax, lx):
        a.set_facecolor(SURF)
        a.set_xlim(-0.5, len(d) - 0.5)
        a.yaxis.tick_right()
        a.grid(axis="y", color=GRID, lw=0.8)
        a.set_axisbelow(True)
        a.tick_params(length=0, pad=5)
        for s in ("top", "left", "right"):
            a.spines[s].set_visible(False)
        a.set_xticks(firsts)
        for i in firsts:
            a.axvline(i - 0.5, color=GRID, lw=0.6, zorder=0)
    ax.set_xticklabels([])
    ax.spines["bottom"].set_visible(False)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v)))
    lx.set_xticklabels(labels, fontsize=10)

    fig.text(0.035, 0.037, "Schattenmodus, nicht belegt. Zustände wie im Pine-Indikator auf TradingView, Kurs: Index-Tageskerzen.\n"
             + name + "\nRisikofenster: 45 Sessions nach dem letzten Tag im Warnzustand. Messfenster des Backtests, kein Ausstiegssignal.",
             color=MUTED, fontsize=8.4, va="center", linespacing=1.5)
    fig.savefig(dest / fname, facecolor=SURF)
    plt.close(fig)
    print("Marker:", [(f"{t:%d.%m.%y}", int(k)) for t, k in mk.items()])
    print(fname, "| Tage", len(d), "| von", d.index[0].date(), "bis", d.index[-1].date(), "| Warn", int(warn.sum()), "| 2er", int(two.sum()),
          "| Fenster", int(win.sum()), "|", state, "|", fenster)


NOTE = " Marker: erster Tag, an dem das Level höher ist als an den 20 Sessions davor."
chart("S&P 500: Gate auf SPY." + NOTE, "S&P 500 · Correction Risk v1.1", "^GSPC", "gate", "dist_high", "level_v10",
      "correction_risk_sp500.png")
chart("NASDAQ 100: Gate auf QQQ." + NOTE, "NASDAQ 100 · Correction Risk v1.1", "^NDX", "gateN", "distN", "levelN",
      "correction_risk_nasdaq.png")
