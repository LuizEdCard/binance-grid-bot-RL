# Reinforcement Learning para Grid Trading Bot

## Visão Geral

Este documento descreve a implementação de Reinforcement Learning (RL) no Grid Trading Bot, baseada na abordagem RLTrading de MattsonThieme. O sistema utiliza um agente de Deep Q-Network (DQN) para otimizar os parâmetros da grade de trading e melhorar o desempenho geral do bot.

## Arquitetura

A implementação de RL consiste em três componentes principais:

1. **RLTradingAgent**: Implementa o agente DQN com memória de experiência para aprender estratégias de trading otimizadas.
2. **TradingEnvironment**: Simula o ambiente de mercado para o agente interagir e aprender.
3. **Integração com GridLogic**: Conecta o agente RL ao sistema de grid trading existente.

## Fluxo de Dados

1. O `GridLogic` fornece o estado atual do mercado e da grade para o agente RL.
2. O agente RL processa esse estado e sugere uma ação (ajuste de parâmetros da grade).
3. O `GridLogic` aplica a ação sugerida e executa o ciclo de trading.
4. O resultado da ação é usado para treinar o agente RL.

## Espaço de Estados

O estado fornecido ao agente RL inclui:

- Mudanças recentes de preço normalizadas
- Estimativa de volatilidade
- Parâmetros da grade (níveis, espaçamento)
- Posição da grade em relação ao preço atual
- Tamanho da posição atual
- PnL não realizado
- Indicadores técnicos (RSI, MACD)
- Métricas de atividade do mercado

## Espaço de Ações

O agente RL pode executar as seguintes ações:

0. Manter parâmetros atuais
1. Aumentar número de níveis
2. Diminuir número de níveis
3. Aumentar espaçamento percentual
4. Diminuir espaçamento percentual
5. Mudar direção da grade para bullish (long)
6. Mudar direção da grade para bearish (short)
7. Resetar para grade balanceada (neutral)
8. Configuração agressiva bullish
9. Configuração agressiva bearish

## Função de Recompensa

A recompensa é calculada com base em:

- Mudança no PnL não realizado
- Número de ordens preenchidas
- Eficiência da grade (quantas ordens foram preenchidas vs. quantas foram colocadas)
- Penalidades por drawdowns excessivos

## Treinamento

O agente é treinado usando:

1. **Replay de Experiência**: Armazena e reutiliza experiências passadas para melhorar a eficiência do treinamento.
2. **Política Epsilon-Greedy**: Equilibra exploração e aproveitamento durante o treinamento.
3. **Treinamento Periódico**: O agente é retreinado após um número configurável de trades.

## Configuração

Os parâmetros de RL podem ser configurados no arquivo `config.yaml`:

```yaml
rl_agent:
  algorithm: "DQN"  # Algoritmo de RL (DQN, PPO, SAC)
  state_size: 30     # Tamanho do vetor de estado
  action_size: 10    # Tamanho do espaço de ações
  learning_rate: 0.001
  batch_size: 32
  buffer_size: 10000  # Tamanho do buffer de replay
  training_timesteps: 10000  # Passos de treinamento por sessão
  episodes: 100       # Número de episódios por sessão
  retraining_trade_threshold: 100  # Retreinar após X trades
```

## Dependências

- TensorFlow >= 2.10.0
- Gymnasium >= 0.28.1
- NumPy
- Pandas
- TA-Lib (opcional, para indicadores técnicos avançados)

## Uso

O sistema de RL é integrado automaticamente ao bot de trading. Quando o bot é iniciado, ele carrega o modelo RL existente (se disponível) ou cria um novo. Durante a operação, o agente RL sugere ajustes para os parâmetros da grade com base nas condições de mercado.

## Monitoramento

O desempenho do agente RL pode ser monitorado através dos logs do sistema, que incluem:

- Ações sugeridas pelo agente
- Recompensas recebidas
- Métricas de treinamento (epsilon, loss)
- Desempenho geral do trading

## Limitações e Trabalho Futuro

- Implementar mais algoritmos de RL (PPO, A2C)
- Melhorar a função de recompensa
- Adicionar mais features ao espaço de estados
- Implementar normalização adaptativa de estados
- Explorar técnicas de meta-aprendizado para adaptação rápida a diferentes condições de mercado