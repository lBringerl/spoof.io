import torch
from torch import optim
import pandas as pd
from joblib import Parallel, delayed
from ppo.config import Config
from ppo.market_env import MarketEnvironment
from ppo.ppo_policy_network import PPOPolicyNetwork
from ppo.utils.log_config import setup_logger
from ppo.train import train_model
from ppo.test import test_model, save_plots

logger = setup_logger('hypertuning', Config.LOG_TRAIN_PATH)

def evaluate_hyperparameters(learning_rate, batch_size, epochs, spoofing_threshold, feature_weights_key):
    logger.info(f"Testing combination: LR={learning_rate}, Batch Size={batch_size}, Epochs={epochs}, Spoofing Threshold={spoofing_threshold}, Feature Weights={feature_weights_key}")

    Config.PPO_CONFIG['learning_rate'] = learning_rate
    Config.PPO_CONFIG['batch_size'] = batch_size
    Config.PPO_CONFIG['n_epochs'] = epochs
    Config.DEFAULT_SPOOFING_THRESHOLD = spoofing_threshold
    Config.FEATURE_WEIGHTS = Config.FEATURE_WEIGHTS_CONFIGS[feature_weights_key]

    try:
        # Training phase
        env = MarketEnvironment(train=True)
        num_features = len(env.reset())
        network = PPOPolicyNetwork(num_features, 2)
        optimizer = optim.Adam(network.parameters(), lr=Config.PPO_CONFIG['learning_rate'])
        loss_data = train_model(env, network, optimizer)

        # Testing phase
        env = MarketEnvironment(train=False)
        model = PPOPolicyNetwork(num_features, 2)
        model.load_state_dict(torch.load(Config.PPO_POLICY_NETWORK_MODEL_PATH))
        model.eval()
        data = test_model(env, model)

        total_reward = data['rewards'].sum()
        logger.info(f"Total Reward for combination LR={learning_rate}, Batch Size={batch_size}, Epochs={epochs}, Spoofing Threshold={spoofing_threshold}, Feature Weights={feature_weights_key}: {total_reward}")

        save_plots(data, loss_data)
        
        return total_reward, learning_rate, batch_size, epochs, spoofing_threshold, feature_weights_key

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

def tune_hyperparameters():
    hyperparameters = Config.HYPERPARAMETERS

    # Phase 1: Compare with and without rolling stats
    rolling_stats_combinations = [
        ('default', 5e-4, 64, 10, 0.8),
        ('no_rolling_stats', 5e-4, 64, 10, 0.8)
    ]
    
    phase1_results = Parallel(n_jobs=-1)(delayed(evaluate_hyperparameters)(
        Config.PPO_CONFIG['learning_rate'], 
        Config.PPO_CONFIG['batch_size'], 
        Config.PPO_CONFIG['n_epochs'], 
        Config.DEFAULT_SPOOFING_THRESHOLD, 
        fw_key
    ) for fw_key, lr, bs, epochs, st in rolling_stats_combinations)

    # Phase 2: Optimizing PPO parameters
    selected_combinations = [
        (1e-4, 128, 20, 0.8),
        (5e-4, 128, 20, 0.8),
        (1e-3, 64, 20, 0.8),
        (5e-4, 64, 20, 0.8),
        (1e-3, 128, 20, 0.7),
        (5e-4, 128, 20, 0.7),
        (1e-3, 64, 20, 0.7),
        (5e-4, 64, 20, 0.7),
        (1e-4, 128, 10, 0.8),
        (1e-4, 64, 10, 0.8)
    ]

    phase2_results = Parallel(n_jobs=-1)(delayed(evaluate_hyperparameters)(
        lr, bs, epochs, st, 'default'
    ) for lr, bs, epochs, st in selected_combinations)

    # Filter out failed runs
    results = [res for res in phase1_results + phase2_results if res is not None]

    # Convert results to DataFrame and save
    df_results = pd.DataFrame(results, columns=['total_reward', 'learning_rate', 'batch_size', 'epochs', 'spoofing_threshold', 'feature_weights'])
    df_results = df_results.sort_values(by='total_reward', ascending=False)  # Sort by total_reward
    df_results.to_csv(Config.OUTPUT_PATH + 'hyperparameter_tuning_results.csv', index=False)
    df_results.to_html(Config.OUTPUT_PATH + 'hyperparameter_tuning_results.html', index=False)
    logger.info("Hyperparameter tuning completed and results saved.")

if __name__ == "__main__":
    tune_hyperparameters()
