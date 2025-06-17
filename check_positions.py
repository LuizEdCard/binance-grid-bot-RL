#!/usr/bin/env python3
from src.utils.api_client import APIClient
import yaml

config_path = 'src/config/config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

try:
    client = APIClient(config, operation_mode='production')
    positions = client.get_futures_positions()
    if positions:
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        print(f'Posições ativas: {len(active_positions)}')
        for pos in active_positions[:5]:
            print(f'  Symbol: {pos["symbol"]}, Size: {pos["positionAmt"]}, Entry: {pos["entryPrice"]}, PNL: {pos["unRealizedProfit"]}')
    else:
        print('Nenhuma posição encontrada')
except Exception as e:
    print(f'Erro: {e}')