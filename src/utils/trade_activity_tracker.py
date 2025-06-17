"""
Trade Activity Tracker - Monitora atividade de trading por par para rotação inteligente
"""
import time
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from .logger import setup_logger

log = setup_logger("trade_activity_tracker")


@dataclass
class PairActivity:
    """Dados de atividade de um par de trading."""
    symbol: str
    last_trade_time: float
    total_trades: int
    total_volume_usdt: float
    avg_trade_size: float
    last_profit: float
    total_profit: float
    consecutive_losses: int
    last_grid_action_time: float
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PairActivity':
        return cls(**data)


class TradeActivityTracker:
    """
    Rastreia atividade de trading para cada par ativo.
    Usado para identificar pares inativos e sugerir rotações.
    """
    
    def __init__(self, data_dir: str = "data", config: dict = None):
        self.data_dir = data_dir
        self.activities_file = os.path.join(data_dir, "trade_activities.json")
        self.activities: Dict[str, PairActivity] = {}
        
        # Configurações obtidas do config.yaml
        if config:
            tracker_config = config.get("trade_activity_tracker", {})
            self.inactivity_timeout = tracker_config.get("inactivity_timeout_seconds", 3600)
            self.min_trade_frequency = tracker_config.get("min_trade_frequency_per_hour", 2)
            self.max_consecutive_losses = tracker_config.get("max_consecutive_losses", 3)
            self._config = config  # Armazenar para uso posterior
        else:
            # Valores padrão apenas se config não for fornecido
            self.inactivity_timeout = 3600
            self.min_trade_frequency = 2
            self.max_consecutive_losses = 3
            self._config = {}
        
        # Garantir que diretório existe
        os.makedirs(data_dir, exist_ok=True)
        
        # Carregar dados existentes
        self._load_activities()
    
    def _load_activities(self) -> None:
        """Carrega atividades salvas do arquivo."""
        try:
            if os.path.exists(self.activities_file):
                with open(self.activities_file, 'r') as f:
                    data = json.load(f)
                    
                for symbol, activity_data in data.items():
                    self.activities[symbol] = PairActivity.from_dict(activity_data)
                
                log.info(f"✅ Carregadas atividades de {len(self.activities)} pares")
            else:
                log.info("📝 Arquivo de atividades não encontrado, iniciando com dados vazios")
                
        except Exception as e:
            log.error(f"Erro ao carregar atividades: {e}")
            self.activities = {}
    
    def _save_activities(self) -> None:
        """Salva atividades no arquivo."""
        try:
            data = {symbol: activity.to_dict() for symbol, activity in self.activities.items()}
            
            with open(self.activities_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            log.error(f"Erro ao salvar atividades: {e}")
    
    def record_trade(self, symbol: str, trade_info: Dict) -> None:
        """
        Registra uma nova transação para um par.
        
        Args:
            symbol: Par de trading (ex: BTCUSDT)
            trade_info: Informações da transação
                Format: {
                    "volume_usdt": float,
                    "profit": float,
                    "trade_type": str,  # "buy", "sell", "grid_fill"
                    "timestamp": float
                }
        """
        try:
            current_time = time.time()
            volume_usdt = float(trade_info.get("volume_usdt", 0))
            profit = float(trade_info.get("profit", 0))
            
            # Inicializar atividade se não existe
            if symbol not in self.activities:
                self.activities[symbol] = PairActivity(
                    symbol=symbol,
                    last_trade_time=current_time,
                    total_trades=0,
                    total_volume_usdt=0.0,
                    avg_trade_size=0.0,
                    last_profit=0.0,
                    total_profit=0.0,
                    consecutive_losses=0,
                    last_grid_action_time=current_time
                )
            
            activity = self.activities[symbol]
            
            # Atualizar dados
            activity.last_trade_time = current_time
            activity.total_trades += 1
            activity.total_volume_usdt += volume_usdt
            activity.avg_trade_size = activity.total_volume_usdt / activity.total_trades
            activity.last_profit = profit
            activity.total_profit += profit
            
            # Rastrear perdas consecutivas
            if profit < 0:
                activity.consecutive_losses += 1
            else:
                activity.consecutive_losses = 0  # Reset se teve lucro
            
            # Salvar alterações
            self._save_activities()
            
            log.debug(f"📊 [{symbol}] Trade registrado: Volume ${volume_usdt:.2f}, Profit ${profit:.2f}, Total trades: {activity.total_trades}")
            
        except Exception as e:
            log.error(f"Erro ao registrar trade para {symbol}: {e}")
    
    def record_grid_action(self, symbol: str, action_type: str) -> None:
        """
        Registra ação do grid (colocação/cancelamento de ordens).
        
        Args:
            symbol: Par de trading
            action_type: Tipo de ação ("place_orders", "cancel_orders", "update_grid")
        """
        try:
            current_time = time.time()
            
            if symbol not in self.activities:
                self.activities[symbol] = PairActivity(
                    symbol=symbol,
                    last_trade_time=0,
                    total_trades=0,
                    total_volume_usdt=0.0,
                    avg_trade_size=0.0,
                    last_profit=0.0,
                    total_profit=0.0,
                    consecutive_losses=0,
                    last_grid_action_time=current_time
                )
            
            self.activities[symbol].last_grid_action_time = current_time
            self._save_activities()
            
            log.debug(f"🔲 [{symbol}] Ação do grid registrada: {action_type}")
            
        except Exception as e:
            log.error(f"Erro ao registrar ação do grid para {symbol}: {e}")
    
    def get_inactive_pairs(self, active_pairs: List[str]) -> List[str]:
        """
        Identifica pares inativos baseado no tempo desde último trade.
        
        Args:
            active_pairs: Lista de pares atualmente ativos
            
        Returns:
            Lista de pares que estão inativos há mais de 1 hora
        """
        try:
            current_time = time.time()
            inactive_pairs = []
            
            for symbol in active_pairs:
                if symbol in self.activities:
                    activity = self.activities[symbol]
                    time_since_last_trade = current_time - activity.last_trade_time
                    
                    if time_since_last_trade > self.inactivity_timeout:
                        inactive_pairs.append(symbol)
                        hours_inactive = time_since_last_trade / 3600
                        log.info(f"⏰ Par inativo detectado: {symbol} (última transação há {hours_inactive:.1f}h)")
                else:
                    # Par sem atividade registrada - considerar inativo
                    inactive_pairs.append(symbol)
                    log.info(f"❓ Par sem histórico de atividade: {symbol}")
            
            return inactive_pairs
            
        except Exception as e:
            log.error(f"Erro ao identificar pares inativos: {e}")
            return []
    
    def get_poor_performing_pairs(self, active_pairs: List[str]) -> List[str]:
        """
        Identifica pares com performance ruim (muitas perdas consecutivas).
        
        Args:
            active_pairs: Lista de pares atualmente ativos
            
        Returns:
            Lista de pares com performance ruim
        """
        try:
            poor_performers = []
            
            for symbol in active_pairs:
                if symbol in self.activities:
                    activity = self.activities[symbol]
                    
                    # Verificar critérios de performance ruim
                    has_consecutive_losses = activity.consecutive_losses >= self.max_consecutive_losses
                    has_negative_total = activity.total_profit < -5.0  # Mais de $5 de prejuízo total
                    
                    if has_consecutive_losses or has_negative_total:
                        poor_performers.append(symbol)
                        log.info(f"📉 Performance ruim detectada: {symbol} (Perdas consecutivas: {activity.consecutive_losses}, Lucro total: ${activity.total_profit:.2f})")
            
            return poor_performers
            
        except Exception as e:
            log.error(f"Erro ao identificar pares com performance ruim: {e}")
            return []
    
    def get_activity_data(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """
        Retorna dados de atividade formatados para uso no pair selector.
        
        Args:
            symbols: Lista específica de símbolos ou None para todos
            
        Returns:
            Dict no formato esperado pelo monitor_atr_quality()
        """
        try:
            activity_data = {}
            current_time = time.time()
            
            symbols_to_check = symbols if symbols else list(self.activities.keys())
            
            for symbol in symbols_to_check:
                if symbol in self.activities:
                    activity = self.activities[symbol]
                    activity_data[symbol] = {
                        "last_trade_time": activity.last_trade_time,
                        "total_trades": activity.total_trades,
                        "inactive_duration": current_time - activity.last_trade_time,
                        "total_profit": activity.total_profit,
                        "consecutive_losses": activity.consecutive_losses,
                        "avg_trade_size": activity.avg_trade_size
                    }
                else:
                    # Par sem atividade - marcar como totalmente inativo
                    activity_data[symbol] = {
                        "last_trade_time": 0,
                        "total_trades": 0,
                        "inactive_duration": float('inf'),
                        "total_profit": 0.0,
                        "consecutive_losses": 0,
                        "avg_trade_size": 0.0
                    }
            
            return activity_data
            
        except Exception as e:
            log.error(f"Erro ao obter dados de atividade: {e}")
            return {}
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas gerais de atividade."""
        try:
            if not self.activities:
                return {"total_pairs": 0, "active_pairs": 0, "inactive_pairs": 0}
            
            current_time = time.time()
            active_count = 0
            total_trades = 0
            total_profit = 0.0
            
            for activity in self.activities.values():
                time_since_last_trade = current_time - activity.last_trade_time
                if time_since_last_trade <= self.inactivity_timeout:
                    active_count += 1
                
                total_trades += activity.total_trades
                total_profit += activity.total_profit
            
            return {
                "total_pairs": len(self.activities),
                "active_pairs": active_count,
                "inactive_pairs": len(self.activities) - active_count,
                "total_trades": total_trades,
                "total_profit": total_profit,
                "inactivity_timeout_hours": self.inactivity_timeout / 3600
            }
            
        except Exception as e:
            log.error(f"Erro ao calcular estatísticas: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = None) -> None:
        """Remove dados antigos para manter arquivo leve."""
        try:
            # Usar configuração se disponível
            if days_to_keep is None:
                days_to_keep = getattr(self, '_config', {}).get("trade_activity_tracker", {}).get("cleanup_days", 7)
            
            current_time = time.time()
            cutoff_time = current_time - (days_to_keep * 24 * 3600)
            
            symbols_to_remove = []
            for symbol, activity in self.activities.items():
                if activity.last_trade_time < cutoff_time and activity.total_trades == 0:
                    symbols_to_remove.append(symbol)
            
            for symbol in symbols_to_remove:
                del self.activities[symbol]
            
            if symbols_to_remove:
                self._save_activities()
                log.info(f"🧹 Removidos {len(symbols_to_remove)} pares inativos antigos")
                
        except Exception as e:
            log.error(f"Erro na limpeza de dados antigos: {e}")


# Factory function para integração fácil
def get_trade_activity_tracker(data_dir: str = "data", config: dict = None) -> TradeActivityTracker:
    """Factory function para criar TradeActivityTracker."""
    return TradeActivityTracker(data_dir, config)