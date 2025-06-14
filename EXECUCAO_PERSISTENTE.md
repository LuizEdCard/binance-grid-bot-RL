# 🚀 Execução Persistente do Trading Bot

Este guia explica como manter o bot rodando continuamente, mesmo após bloqueio de tela, usando **tmux**.

## 📋 Scripts Disponíveis

### 1. `start_persistent_bot.sh` - Iniciar Bot Persistente
```bash
./start_persistent_bot.sh
```

**O que faz:**
- ✅ Instala tmux automaticamente se não estiver instalado
- ✅ Cria sessão em background que continua rodando após bloqueio de tela
- ✅ Detecta se já existe uma sessão ativa
- ✅ Ativa ambiente virtual automaticamente
- ✅ Conecta à sessão automaticamente

### 2. `monitor_bot.sh` - Monitorar Bot Remotamente
```bash
./monitor_bot.sh
```

**Opções disponíveis:**
- 📊 Ver logs em tempo real
- 🔗 Conectar à sessão do bot
- 📈 Status rápido das posições  
- 💰 Verificar saldo
- 🛑 Parar o bot
- ❌ Sair

## 🎯 Comandos Úteis do Tmux

### Comandos Básicos
```bash
# Ver sessões ativas
tmux list-sessions

# Conectar à sessão do bot
tmux attach -t trading-bot

# Sair da sessão SEM parar o bot
Ctrl+B, depois D (detach)

# Parar completamente o bot
tmux kill-session -t trading-bot
```

### Dentro da Sessão
- **Sair sem parar bot**: `Ctrl+B` → `D`
- **Scroll para cima**: `Ctrl+B` → `[` → Use setas
- **Sair do scroll**: `Q`

## 🔍 Verificação de Status

### Ver se o bot está rodando
```bash
tmux list-sessions | grep trading-bot
```

### Verificar logs rapidamente
```bash
tail -f logs/bot.log
tail -f src/logs/bot.log
```

### Status das posições
```bash
tail -5 src/logs/pairs/*.log
```

## 🚨 Situação Atual do Sistema

### ⚠️ Status do Capital
- **Saldo Atual**: ~$5.40 USDT
- **Mínimo Binance**: $5.00 USDT por ordem
- **Status**: Capital INSUFICIENTE para novos pares

### 📊 Posição Ativa
- **Par**: DOGEUSDT  
- **Tipo**: SHORT -30.0000 DOGE
- **Leverage**: 10x
- **Status**: Operando normalmente

### 💡 Para Operar Mais Pares
É necessário:
1. **Depósito adicional** de pelo menos $5-10 USDT, OU
2. **Aguardar lucros** da posição DOGEUSDT existente

## 🛠️ Soluções para Problemas Comuns

### Bot para quando tela bloqueia
```bash
# Use o script persistente
./start_persistent_bot.sh
```

### Telegram com erro de connection pool
✅ **JÁ CORRIGIDO** - Melhorada configuração de connection pool

### RiskAgent com erro 'list' object
✅ **JÁ CORRIGIDO** - Adicionada validação de tipos

### GridLogic sem método _round_price  
✅ **JÁ CORRIGIDO** - Adicionados métodos de arredondamento

## 📱 Notificações Telegram

O bot enviará notificações para:
- ✅ Início/parada do sistema
- 📊 Alertas de risco
- 💰 Trades executados  
- ⚠️ Erros críticos

## 🔄 Fluxo Recomendado

1. **Iniciar bot persistente:**
   ```bash
   ./start_persistent_bot.sh
   ```

2. **Verificar se está funcionando:**
   ```bash
   ./monitor_bot.sh
   # Escolher opção 1 para ver logs
   ```

3. **Sair sem parar bot:**
   - Dentro da sessão: `Ctrl+B` → `D`
   - Ou fechar terminal normalmente

4. **Reconectar quando necessário:**
   ```bash
   ./monitor_bot.sh
   # Escolher opção 2 para conectar
   ```

## 📈 Próximos Passos

### Para Melhor Performance
1. **Aumentar capital** para $15-20 USDT (permitir 3-4 pares)
2. **Monitorar posição DOGEUSDT** para fechar com lucro
3. **Verificar logs regularmente** usando `./monitor_bot.sh`

### Para Desenvolvimento
- Logs detalhados em `src/logs/pairs/[SYMBOL].log`
- Métricas do sistema em `logs/bot.log`
- Configurações em `src/config/config.yaml`

---

**🎯 O bot agora roda de forma PERSISTENTE e segura, respeitando os limites da Binance!**