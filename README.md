# Grid Trading Bot com RL e Análise de Sentimento

## Visão Geral

Este projeto implementa um bot de trading automatizado para a Binance Futures, focado na estratégia de Grid Trading. O bot é aprimorado com:

*   **Aprendizado por Reforço (RL):** Utiliza `stable-baselines3` para otimizar dinamicamente parâmetros da grade (como espaçamento e possivelmente direção) com base na experiência de mercado.
*   **Análise Técnica Avançada:** Integra a biblioteca `TA-Lib` (requer instalação manual) para calcular indicadores como ATR, ADX e reconhecer padrões de candlestick, usados no gerenciamento de risco e seleção de pares.
*   **Análise de Sentimento de Mercado:**
    *   Utiliza um modelo LLM leve (`llmware/slim-sentiment-onnx`) rodando localmente via `onnxruntime` para analisar o sentimento de textos.
    *   Coleta dados de redes sociais (atualmente Reddit via `praw`) para alimentar a análise de sentimento.
    *   Utiliza o score de sentimento resultante para:
        *   Gerar **alertas** via Telegram.
        *   **Ajustar o risco** dinamicamente (reduzindo alavancagem em sentimento negativo).
        *   **Filtrar a seleção de novos pares** (evitando entradas com sentimento muito baixo).
        *   Servir como **feature adicional para o agente RL**.
*   **Gerenciamento de Risco Robusto:** Inclui stop loss dinâmico (baseado em ATR ou percentual), proteção de lucro, circuit breakers e ajuste de risco por sentimento.
*   **Seleção Inteligente de Pares:** Filtra pares com base em volume, volatilidade (ATR), tendência (ADX), sentimento e, opcionalmente, padrões de candlestick.
*   **Execução Concorrente:** Projetado para rodar múltiplos pares de trading simultaneamente (a implementação exata da concorrência pode variar).
*   **Modos de Operação:** Suporta modo `Production` (operações reais) e `Shadow` (simulação em tempo real).

## 1. Instalação

**Pré-requisitos:**

*   Python 3.9+
*   Pip (gerenciador de pacotes Python)
*   **TA-Lib (Biblioteca C):** Esta é a dependência mais crítica e **precisa ser instalada manualmente** no seu sistema operacional *antes* de instalar as dependências Python. Siga as instruções no arquivo `talib_installation_guide.md`.

**Passos:**

1.  **Clone o Repositório:**
    ```bash
    git clone <url_do_seu_repositorio> # Substitua pela URL correta
    cd <nome_da_pasta_do_repositorio>
    ```
2.  **Instale a Biblioteca TA-Lib C:** Siga **rigorosamente** as instruções do `talib_installation_guide.md` para o seu sistema operacional (Windows ou Linux).
3.  **Crie um Ambiente Virtual (Recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate # Linux/macOS
    # OU
    .\venv\Scripts\activate # Windows
    ```
4.  **Instale as Dependências Python:**
    ```bash
    pip install -r requirements.txt
    ```
    *Observação:* A instalação pode demorar, especialmente devido ao `tensorflow`.

## 2. Configuração

Todas as configurações principais são feitas em dois arquivos dentro da pasta `src/config/`:

*   **`.env`:** Armazena informações sensíveis (chaves de API, tokens). Crie este arquivo a partir do `.env.example` (se existir) ou manualmente.
    *   `BINANCE_API_KEY`: Sua chave de API da Binance.
    *   `BINANCE_API_SECRET`: Seu segredo de API da Binance.
    *   `TELEGRAM_BOT_TOKEN` (Opcional): Token do seu bot do Telegram para alertas.
    *   `TELEGRAM_CHAT_ID` (Opcional): ID do chat do Telegram para receber alertas.
    *   `REDDIT_CLIENT_ID` (Opcional): Client ID da sua aplicação Reddit API (necessário para análise de sentimento real).
    *   `REDDIT_CLIENT_SECRET` (Opcional): Client Secret da sua aplicação Reddit API.
    *   `REDDIT_USER_AGENT` (Opcional): User agent para a API do Reddit (ex: `python:meu_bot:v1.0 (by u/seu_usuario)`).
*   **`config.yaml`:** Define os parâmetros operacionais do bot.
    *   `exchange`: Configurações da exchange (atualmente focado em `binance_futures`).
    *   `grid`: Parâmetros iniciais da grade (níveis, alavancagem, espaçamento).
    *   `trading`: Configurações gerais de trading (capital por par, máximo de pares, intervalo de ciclo).
    *   `rl_agent`: Parâmetros do agente RL (algoritmo, features, função de recompensa, frequência de treino).
    *   `pair_selection`: Critérios para selecionar pares (volume, ATR, ADX, blacklist, filtros opcionais).
    *   `risk_management`: Regras de gerenciamento de risco (drawdown máximo, SL, TP, proteção de lucro).
    *   `logging`: Configurações de log (nível, arquivos, console).
    *   `alerts`: Habilita/desabilita alertas e configura destinos (requer tokens no `.env`).
    *   **`sentiment_analysis` (NOVO):**
        *   `enabled`: `True` para ativar toda a funcionalidade de análise de sentimento.
        *   `fetch_interval_minutes`: Frequência de busca de dados sociais.
        *   `smoothing_window`: Janela para suavizar o score de sentimento final.
        *   `reddit`: Configurações específicas do Reddit (subreddits, limites, filtro de tempo).
        *   `alerts`: Configurações para alertas baseados em sentimento (limiares, cooldown).
        *   `risk_adjustment`: Regras para ajuste de risco por sentimento (limiar de redução, fator).
        *   `pair_filtering`: Regras para filtrar novos pares por sentimento (limiar mínimo).
        *   `rl_feature`: `True` para incluir o score de sentimento no estado do RL.
    *   `operation_mode`: `Production` ou `Shadow`.

## 3. Executando o Bot

1.  **Certifique-se de que as configurações** (`.env` e `config.yaml`) estão corretas.
2.  **Ative o ambiente virtual** (se estiver usando um).
3.  **Use o script de inicialização (recomendado):**
    ```bash
    bash start_bot.sh
    ```
    Ou execute diretamente o ponto de entrada principal (verifique o nome correto, pode ser `main.py` ou `bot_logic.py`):
    ```bash
    python src/main.py # ou python src/bot_logic.py
    ```

## 4. Funcionalidades Detalhadas

*   **Grid Trading:** Cria uma grade de ordens de compra e venda em torno do preço atual. O RL pode ajustar o espaçamento e a direção.
*   **Aprendizado por Reforço (RL):**
    *   Treina um agente (PPO ou SAC) para tomar decisões ótimas.
    *   O ambiente (`src/rl/environment.py`) simula o mercado e fornece o estado (indicadores, posição, **sentimento**).
    *   O treinamento pode ser iniciado separadamente (ver `src/rl/train_rl_agent.py`) ou ocorrer periodicamente durante a execução do bot (configurável).
*   **Análise de Sentimento:**
    *   **Coleta (Reddit):** Busca posts/comentários em subreddits definidos.
    *   **Análise (LLM):** Usa `llmware/slim-sentiment-onnx` para classificar o texto.
    *   **Score:** Calcula um score agregado (-1 a 1).
    *   **Ações:** Dispara alertas, ajusta risco, filtra pares e informa o RL.
    *   **Modo Mock:** É possível testar sem credenciais reais do Reddit. Modifique a inicialização do `SocialListener` em `src/bot_logic.py` para `SocialListener(mock_mode=True)`.
*   **Gerenciamento de Risco:**
    *   Stop Loss (ATR ou %).
    *   Proteção de Lucro.
    *   Circuit Breaker (Drawdown, Falha API).
    *   Ajuste de Alavancagem por Sentimento.
*   **Seleção de Pares:**
    *   Filtros: Volume, ATR, ADX, Spread (placeholder), Padrões Candlestick (opcional, requer TA-Lib), Sentimento (opcional).
    *   Ranking: Prioriza maior ATR e menor ADX.

## 5. Treinamento do Modelo RL

O script `src/rl/train_rl_agent.py` (ou similar) é usado para treinar o modelo RL offline usando dados históricos. Certifique-se de ter dados históricos adequados e configure os parâmetros de treinamento no `config.yaml`.

## 6. Logs e Monitoramento

Verifique os arquivos de log definidos na seção `logging` do `config.yaml` para monitorar a operação do bot e diagnosticar problemas.

## Contribuição

[Adicione informações sobre como contribuir, se aplicável]

## Licença

[Adicione informações sobre a licença do projeto]

