import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import pyRofex
from dotenv import load_dotenv
from matplotlib.patches import Rectangle

load_dotenv(os.path.join(os.path.dirname(__file__), "../futuros_soja/.env"))

user = os.getenv("ROFEX_USER")
password = os.getenv("ROFEX_PASSWORD")
account = os.getenv("ROFEX_ACCOUNT")
pyRofex.initialize(
    user=user,
    password=password,
    account=account,
    environment=pyRofex.Environment.REMARKET,
)

soja_ticker = "SOJ.ROS/NOV26"
dlr_ticker = "DLR/NOV26"
today = datetime.now()
start = today - timedelta(days=30)
start_str = start.strftime("%Y-%m-%d")
end_str = today.strftime("%Y-%m-%d")


def trades_to_ohlc(ticker, start, end):
    resp = pyRofex.get_trade_history(ticker=ticker, start_date=start, end_date=end)
    if not resp or "trades" not in resp:
        return None
    d = {}
    for t in resp["trades"]:
        date = t["datetime"][:10]
        p = t["price"]
        if date not in d:
            d[date] = {"open": p, "high": p, "low": p, "close": p}
        else:
            d[date]["high"] = max(d[date]["high"], p)
            d[date]["low"] = min(d[date]["low"], p)
            d[date]["close"] = p
    dates = sorted(d.keys())
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": [d[x]["open"] for x in dates],
            "high": [d[x]["high"] for x in dates],
            "low": [d[x]["low"] for x in dates],
            "close": [d[x]["close"] for x in dates],
        }
    )


print(f"Fetching {soja_ticker}...")
soja = trades_to_ohlc(soja_ticker, start_str, end_str)
if soja is None:
    print("No soja data")
    exit(1)
print(f"  {len(soja)} records")

print(f"Fetching {dlr_ticker}...")
dlr = trades_to_ohlc(dlr_ticker, start_str, end_str)
if dlr is None:
    print("No DLR data")
    exit(1)
print(f"  {len(dlr)} records")

# Merge on date
soja["date_only"] = soja["date"].dt.date
dlr["date_only"] = dlr["date"].dt.date
merged = soja.merge(
    dlr[["date_only", "close"]], on="date_only", how="left", suffixes=("_soja", "_dlr")
)
merged.rename(columns={"close_dlr": "tc_usd_ars"}, inplace=True)
merged["tc_usd_ars"] = merged["tc_usd_ars"].ffill()

# Multiply by exchange rate
merged["close_ars"] = merged["close_soja"] * merged["tc_usd_ars"]
merged["open_ars"] = merged["open"] * merged["tc_usd_ars"]
merged["high_ars"] = merged["high"] * merged["tc_usd_ars"]
merged["low_ars"] = merged["low"] * merged["tc_usd_ars"]

# Save Excel
out = merged[
    ["date", "tc_usd_ars", "open_ars", "high_ars", "low_ars", "close_ars"]
].copy()
out.columns = ["date", "tc_usd_ars", "open_ars", "high_ars", "low_ars", "close_ars"]
out.to_excel("soja_pesos.xlsx", index=False)
print(f"Saved soja_pesos.xlsx")

# Chart
fig, ax = plt.subplots(figsize=(14, 7))
for i in range(len(merged)):
    o = merged.iloc[i]["open_ars"]
    c = merged.iloc[i]["close_ars"]
    h = merged.iloc[i]["high_ars"]
    l = merged.iloc[i]["low_ars"]
    color = "green" if c >= o else "red"
    ax.plot([i, i], [l, h], color=color, linewidth=2)
    height = abs(c - o)
    bottom = min(o, c)
    rect = Rectangle(
        (i - 0.3, bottom), 0.6, height, facecolor=color, edgecolor=color, alpha=0.8
    )
    ax.add_patch(rect)

ax.set_xlabel("Fecha", fontweight="bold")
ax.set_ylabel("Precio (ARS)", fontweight="bold")
ax.set_title(
    f"Futuros Soja en Pesos\n{soja_ticker} x {dlr_ticker} (ROFEX)",
    fontweight="bold",
    fontsize=14,
)
ax.grid(True, alpha=0.3)

tick_pos = list(range(0, len(merged), max(1, len(merged) // 10)))
tick_labels = [merged.iloc[i]["date"].strftime("%Y-%m-%d") for i in tick_pos]
ax.set_xticks(tick_pos)
ax.set_xticklabels(tick_labels, rotation=45, ha="right")

plt.tight_layout()
plt.savefig("soja_pesos_grafico.jpg", dpi=150, format="jpg")
print("Saved soja_pesos_grafico.jpg")

print("\nArchivos generados:")
print("  soja_pesos.xlsx")
print("  soja_pesos_grafico.jpg")

"""
Justificación:
- Sin OOP ni lambda, funciones minimas
- Obtiene trades de soja (USD) y DLR/NOV26 (TC USD/ARS) ambos de ROFEX
- Mergea por fecha, multiplica precio USD x TC = precio ARS
- Grafico velas con precios en pesos
"""

# Agents.md rules applied successfully
