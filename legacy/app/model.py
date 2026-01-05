import numpy as np
import pandas as pd
import os

class TradingEnv:
    def __init__(self, ticker: str, window_size: int = 10):
        filepath = os.path.join("data", f"{ticker}.csv")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        self.data = pd.read_csv(filepath)
        self.window_size = window_size

    def reset(self):
        self.current_step = self.window_size
        self.balance = 1.0
        self.shares_held = 0
        return self._get_state()

    def _get_state(self):
        start = self.current_step - self.window_size
        window = self.data["Close"].values[start:self.current_step]
        norm_window = (window / window[0]) - 1.0
        return norm_window.reshape(-1, 1)

    def step(self, action: int):
        price = self.data["Close"].iloc[self.current_step]
        reward = 0.0

        if action == 1 and self.balance > 0:
            self.shares_held = self.balance / price
            self.balance = 0.0
        elif action == 2 and self.shares_held > 0:
            self.balance = self.shares_held * price
            self.shares_held = 0
            reward = self.balance - 1.0

        self.current_step += 1
        done = self.current_step >= len(self.data)
        next_state = self._get_state() if not done else None
        return next_state, reward, done
