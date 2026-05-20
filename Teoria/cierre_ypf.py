import yfinance as yf
import matplotlib.pyplot as plt

ypf = yf.Ticker("YPF")
hist = ypf.history(period="ytd")

hist["EMA21"] = hist["Close"].ewm(span=21, adjust=False).mean()

plt.figure(figsize=(12, 5))
plt.plot(hist.index, hist["Close"], linewidth=1.5, color="steelblue", label="Cierre")
plt.plot(hist.index, hist["EMA21"], linewidth=1.5, color="orange", label="EMA 21")
plt.legend()
plt.title("YPF - Precio de Cierre (último año)")
plt.xlabel("Fecha")
plt.ylabel("Precio de Cierre (USD)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("cierre_ypf.png", dpi=150)
plt.show()
