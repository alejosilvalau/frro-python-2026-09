import yfinance as yf
import json

apple = yf.Ticker("AAPL")

print(json.dumps(apple.info))

