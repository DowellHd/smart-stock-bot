dimport numpy as np
from app.model import TradingEnv
from app.agent import DQNAgent

def train(
    ticker: str = "AAPL",
    episodes: int = 50,
    window_size: int = 10,
    batch_size: int = 32,
):
    # 1) Initialize environment & agent
    env = TradingEnv(ticker, window_size=window_size)
    state_shape = env._get_state().shape   # e.g. (window_size, 1)
    agent = DQNAgent(state_shape=state_shape, action_size=3)

    for e in range(1, episodes + 1):
        state = env.reset()
        total_reward = 0.0
        done = False

        while not done:
            # 2) Agent picks action
            action = agent.act(state)

            # 3) Environment responds
            next_state, reward, done = env.step(action)

            # 4) Store experience
            agent.remember(state, action, reward, next_state, done)
            state = next_state
            total_reward += reward

            # 5) Train on a batch
            agent.replay(batch_size)

        print(f"Episode {e}/{episodes} — Total Reward: {total_reward:.2f}, Epsilon: {agent.epsilon:.4f}")

        # Save a checkpoint every 10 episodes
        if e % 10 == 0:
            agent.model.save(f"models/dqn_{ticker}_ep{e}.h5")

    # Final save
    agent.model.save(f"models/dqn_{ticker}_final.h5")

if __name__ == "__main__":
    train()
