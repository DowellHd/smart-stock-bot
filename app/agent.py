# app/agent.py

import random
import numpy as np
from collections import deque
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense, Flatten
from tensorflow.keras.optimizers import Adam

class DQNAgent:
    def __init__(
        self,
        state_shape: tuple,
        action_size: int,
        memory_size: int = 2000,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.995,
        learning_rate: float = 0.001,
    ):
        self.state_shape = state_shape          # e.g. (window_size, 1)
        self.action_size = action_size          # 3 actions: hold, buy, sell
        self.memory = deque(maxlen=memory_size) # replay buffer
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.learning_rate = learning_rate
        self.model = self._build_model()

    def _build_model(self) -> Sequential:
        """Builds and compiles the Q‑network."""
        model = Sequential()
        model.add(Flatten(input_shape=self.state_shape))
        model.add(Dense(24, activation='relu'))
        model.add(Dense(24, activation='relu'))
        model.add(Dense(self.action_size, activation='linear'))
        model.compile(loss='mse', optimizer=Adam(learning_rate=self.learning_rate))
        return model

    def remember(self, state, action, reward, next_state, done):
        """Store experience in replay buffer."""
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        """ε‑greedy action selection."""
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        q_vals = self.model.predict(state[np.newaxis, :], verbose=0)
        return np.argmax(q_vals[0])

    # (We’ll add replay() and train() methods next)
    def replay(self, batch_size: int = 32):
        """
        Sample a random minibatch and train the Q‑network.
        """
        if len(self.memory) < batch_size:
            return  # not enough samples yet

        minibatch = random.sample(self.memory, batch_size)
        for state, action, reward, next_state, done in minibatch:
            # compute target Q-value
            target = reward
            if not done:
                future_q = self.model.predict(next_state[np.newaxis, :], verbose=0)[0]
                target += self.gamma * np.max(future_q)

            # update the Q-network
            target_f = self.model.predict(state[np.newaxis, :], verbose=0)
            target_f[0][action] = target
            self.model.fit(state[np.newaxis, :], target_f, epochs=1, verbose=0)

        # decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
