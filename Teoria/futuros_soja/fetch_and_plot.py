import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import pyRofex
from dotenv import load_dotenv
from matplotlib.patches import Rectangle

# Load env vars
load_dotenv()
user = os.getenv("ROFEX_USER")
password = os.getenv("ROFEX_PASSWORD")
account = os.getenv("ROFEX_ACCOUNT")

# Connect to ROFEX
pyRofex.initialize(
    user=user,
    password=password,
    account=account,
    environment=pyRofex.Environment.REMARKET,
)

# Get SOJ.ROS/NOV26 data
ticker = "SOJ.ROS/NOV26"
print(f"Fetching {ticker}...")

try:
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    start_date_str = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    print(f"Date range: {start_date_str} to {end_date_str}")

    trades = pyRofex.get_trade_history(
        ticker=ticker, start_date=start_date_str, end_date=end_date_str
    )

    if not trades or "trades" not in trades:
        print("No data received")
        exit(1)

    # Parse trade data - group by date for candlestick
    data = trades["trades"]

    # Group by date to create candlesticks
    dates_dict = {}
    for trade in data:
        trade_date = trade["datetime"][:10]  # YYYY-MM-DD
        price = trade["price"]

        if trade_date not in dates_dict:
            dates_dict[trade_date] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }
        else:
            dates_dict[trade_date]["high"] = max(dates_dict[trade_date]["high"], price)
            dates_dict[trade_date]["low"] = min(dates_dict[trade_date]["low"], price)
            dates_dict[trade_date]["close"] = price

    # Convert to DataFrame
    dates = []
    opens = []
    highs = []
    lows = []
    closes = []

    for date in sorted(dates_dict.keys()):
        dates.append(pd.to_datetime(date))
        opens.append(dates_dict[date]["open"])
        highs.append(dates_dict[date]["high"])
        lows.append(dates_dict[date]["low"])
        closes.append(dates_dict[date]["close"])

    df = pd.DataFrame(
        {"date": dates, "open": opens, "high": highs, "low": lows, "close": closes}
    )

    # Save to Excel
    excel_path = "soja_precios.xlsx"
    df.to_excel(excel_path, index=False, sheet_name="SOJ.ROS.NOV26")
    print(f"Data saved to {excel_path}")
    print(f"Total records: {len(df)}")
    print(df.head())

    # Create candlestick chart
    fig, ax = plt.subplots(figsize=(14, 7))

    width = 0.6

    for i in range(len(df)):
        date = df.iloc[i]["date"]
        open_price = df.iloc[i]["open"]
        close_price = df.iloc[i]["close"]
        high_price = df.iloc[i]["high"]
        low_price = df.iloc[i]["low"]

        # Color: green if close > open, red if close < open
        color = "green" if close_price >= open_price else "red"

        # High-Low line
        ax.plot([i, i], [low_price, high_price], color=color, linewidth=2)

        # Open-Close rectangle
        height = abs(close_price - open_price)
        bottom = min(open_price, close_price)
        rect = Rectangle(
            (i - width / 2, bottom),
            width,
            height,
            facecolor=color,
            edgecolor=color,
            alpha=0.8,
        )
        ax.add_patch(rect)

    ax.set_xlabel("Fecha", fontweight="bold")
    ax.set_ylabel("Precio (USD)", fontweight="bold")
    ax.set_title(f"Gráfico de Velas - {ticker}", fontweight="bold", fontsize=14)
    ax.grid(True, alpha=0.3)

    # Format x-axis with dates
    tick_positions = list(range(0, len(df), max(1, len(df) // 10)))
    tick_labels = [df.iloc[i]["date"].strftime("%Y-%m-%d") for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha="right")

    plt.tight_layout()

    # Save as JPG
    jpg_path = "soja_grafico.jpg"
    plt.savefig(jpg_path, dpi=150, format="jpg")
    print(f"Chart saved to {jpg_path}")

    # Create HTML
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gráfico de Futuros de Soja</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        .info {{
            background-color: #e8f4f8;
            padding: 10px;
            border-left: 4px solid #0066cc;
            margin-bottom: 20px;
        }}
        img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Análisis de Futuros de Soja</h1>
        <div class="info">
            <p><strong>Símbolo:</strong> {ticker}</p>
            <p><strong>Período:</strong> {df.iloc[0]['date'].strftime('%Y-%m-%d')} a {df.iloc[-1]['date'].strftime('%Y-%m-%d')}</p>
            <p><strong>Total de registros:</strong> {len(df)}</p>
        </div>
        <img src="soja_grafico.jpg" alt="Gráfico de Velas - {ticker}">
        <div class="footer">
            <p>Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Datos obtenidos desde ROFEX (Matba Rofex)</p>
        </div>
    </div>
</body>
</html>
"""

    html_path = "soja_analisis.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML saved to {html_path}")

    print("\nTareas completadas:")
    print(f"✓ Datos guardados en {excel_path}")
    print(f"✓ Gráfico guardado en {jpg_path}")
    print(f"✓ HTML generado en {html_path}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()

"""
Justificación:
- Script minimalista sin OOP ni lambda
- Usa get_trade_history de pyRofex (API disponible)
- Agrupa trades por fecha para crear candlesticks
- Guarda Excel, JPG y HTML como pide tarea
- Colores: verde (close >= open), rojo (close < open)
- matplotlib para graficar velas (high-low líneas, open-close rectángulos)
"""

# Agents.md rules applied successfully
