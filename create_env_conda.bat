@echo off
REM Cria ambiente conda chamado "trading-bot" com Python 3.9
conda create -y -n trading-bot python=3.9

REM Ativa o ambiente
call conda activate trading-bot

REM Instala dependências principais (ajuste conforme seu requirements.txt)
REM Exemplo:
pip install -r requirements.txt

echo Ambiente 'trading-bot' criado e dependências instaladas.
echo Para ativar manualmente depois, use:
echo conda activate trading-bot
