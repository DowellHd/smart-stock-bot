# train/fetch_data.py
import yfinance as yf
import pandas as pd
import os

def fetch_and_save(ticker: str, start: str="2020-01-01", end: str=None):
    """
    Downloads historical data for `ticker` and saves to data/{ticker}.csv.
    """
    os.makedirs("data", exist_ok=True)
    df = yf.download(ticker, start=start, end=end)
    df.to_csv(f"data/{ticker}.csv")
    print(f"Saved {ticker}.csv — {len(df)} rows")

if __name__ == "__main__":
    for symbol in ["AAPL", "TSLA"]:
        fetch_and_save(symbol)
