"""
Sistema de armazenamento de dados para modo Shadow e treinamento RL.
Salva estados de mercado, ações e resultados para uso posterior.
"""

import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
import logging

log = logging.getLogger(__name__)

class ShadowDataStorage:
    """Gerencia armazenamento de dados simulados para treinamento RL."""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.trades_file = os.path.join(data_dir, "shadow_trades.jsonl")
        self.states_file = os.path.join(data_dir, "market_states.jsonl") 
        self.actions_file = os.path.join(data_dir, "rl_actions.jsonl")
        self.performance_file = os.path.join(data_dir, "performance.jsonl")
        
        # Criar diretório se não existir
        os.makedirs(data_dir, exist_ok=True)
        
        log.info(f"ShadowDataStorage inicializado: {data_dir}")
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Salva dados de trade simulado."""
        trade_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "shadow_trade",
            **trade_data
        }
        
        self._append_to_file(self.trades_file, trade_entry)
        log.debug(f"Trade simulado salvo: {trade_data['symbol']} {trade_data['side']}")
    
    def log_market_state(self, symbol: str, state: List[float], price: float):
        """Salva estado de mercado capturado."""
        state_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "current_price": price,
            "state_vector": state,
            "state_size": len(state)
        }
        
        self._append_to_file(self.states_file, state_entry)
        log.debug(f"Estado de mercado salvo: {symbol} @ {price}")
    
    def log_rl_action(self, symbol: str, state: List[float], action: int, 
                     reward: float = None, next_state: List[float] = None):
        """Salva ação do RL e contexto."""
        action_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state
        }
        
        self._append_to_file(self.actions_file, action_entry)
        log.debug(f"Ação RL salva: {symbol} action={action}")
    
    def log_performance(self, symbol: str, metrics: Dict[str, float]):
        """Salva métricas de performance."""
        perf_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            **metrics
        }
        
        self._append_to_file(self.performance_file, perf_entry)
        log.debug(f"Performance salva: {symbol}")
    
    def _append_to_file(self, filepath: str, data: Dict[str, Any]):
        """Adiciona linha ao arquivo JSONL."""
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        except Exception as e:
            log.error(f"Erro ao salvar dados em {filepath}: {e}")
    
    def load_trades_df(self, symbol: str = None, last_days: int = None) -> pd.DataFrame:
        """Carrega trades como DataFrame para análise."""
        try:
            if not os.path.exists(self.trades_file):
                return pd.DataFrame()
            
            trades = []
            with open(self.trades_file, 'r', encoding='utf-8') as f:
                for line in f:
                    trade = json.loads(line.strip())
                    if symbol is None or trade.get('symbol') == symbol:
                        trades.append(trade)
            
            df = pd.DataFrame(trades)
            if df.empty:
                return df
                
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if last_days:
                cutoff = datetime.now() - pd.Timedelta(days=last_days)
                df = df[df['timestamp'] >= cutoff]
            
            return df.sort_values('timestamp')
            
        except Exception as e:
            log.error(f"Erro ao carregar trades: {e}")
            return pd.DataFrame()
    
    def load_training_data(self, symbol: str = None, limit: int = 10000) -> Dict[str, List]:
        """Carrega dados para treinamento RL (estados, ações, rewards)."""
        try:
            if not os.path.exists(self.actions_file):
                return {"states": [], "actions": [], "rewards": [], "next_states": []}
            
            states, actions, rewards, next_states = [], [], [], []
            
            with open(self.actions_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                        
                    action_data = json.loads(line.strip())
                    if symbol is None or action_data.get('symbol') == symbol:
                        if (action_data.get('state') and 
                            action_data.get('action') is not None and
                            action_data.get('reward') is not None):
                            
                            states.append(action_data['state'])
                            actions.append(action_data['action'])
                            rewards.append(action_data['reward'])
                            next_states.append(action_data.get('next_state', action_data['state']))
            
            log.info(f"Dados de treinamento carregados: {len(states)} samples")
            return {
                "states": states,
                "actions": actions, 
                "rewards": rewards,
                "next_states": next_states
            }
            
        except Exception as e:
            log.error(f"Erro ao carregar dados de treinamento: {e}")
            return {"states": [], "actions": [], "rewards": [], "next_states": []}
    
    def get_data_stats(self) -> Dict[str, int]:
        """Retorna estatísticas dos dados salvos."""
        stats = {}
        
        for name, filepath in [
            ("trades", self.trades_file),
            ("states", self.states_file), 
            ("actions", self.actions_file),
            ("performance", self.performance_file)
        ]:
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        count = sum(1 for _ in f)
                    stats[name] = count
                else:
                    stats[name] = 0
            except:
                stats[name] = 0
        
        return stats

# Instância global para uso em todo o projeto
shadow_storage = ShadowDataStorage()