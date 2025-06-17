# Sistema de Gerenciamento Multi-Agente

Este documento descreve o sistema completo de gerenciamento dos processos multi-agente do bot de trading.

## 📋 Visão Geral

O sistema multi-agente foi finalizado e agora inclui um conjunto completo de ferramentas de gerenciamento que permite:

- ✅ Iniciar o sistema completo ou componentes individuais
- ✅ Parar todos os processos de forma elegante
- ✅ Monitorar o status em tempo real
- ✅ Visualizar logs e métricas
- ✅ Fazer health checks automáticos
- ✅ Limpar arquivos temporários e cache

## 🛠️ Scripts de Gerenciamento

### Script Principal: `manage_multi_agent.sh`
Interface central unificada para todas as operações.

```bash
# Uso interativo (menu)
./manage_multi_agent.sh

# Uso direto com comandos
./manage_multi_agent.sh start
./manage_multi_agent.sh stop
./manage_multi_agent.sh status
./manage_multi_agent.sh restart
```

### Scripts Especializados

1. **`stop_multi_agent_system.sh`** - Parada elegante de todos os processos
2. **`check_multi_agent_status.sh`** - Verificação completa de status
3. **Existentes:**
   - `start_multi_agent_bot.sh` - Iniciar apenas o bot
   - `start_complete_system.sh` - Sistema completo
   - `monitor_bot.sh` - Monitoramento

## 🚀 Como Usar

### Finalizar Todos os Processos
```bash
# Método 1: Script direto
./stop_multi_agent_system.sh

# Método 2: Via gerenciador
./manage_multi_agent.sh stop

# Método 3: Comando manual
pkill -f multi_agent_bot.py
```

### Verificar Status
```bash
# Status completo
./check_multi_agent_status.sh

# Status rápido
./manage_multi_agent.sh health

# Via gerenciador interativo
./manage_multi_agent.sh
# Depois escolher opção 4 (status)
```

### Iniciar Sistema
```bash
# Sistema completo (Bot + API + Frontend)
./start_complete_system.sh

# Apenas o bot multi-agente
./start_multi_agent_bot.sh

# Via gerenciador (com opções)
./manage_multi_agent.sh start
```

### Monitoramento
```bash
# Monitoramento contínuo
./manage_multi_agent.sh monitor

# Logs em tempo real
./manage_multi_agent.sh logs

# Monitor específico
./monitor_bot.sh
```

## 📊 Funcionalidades dos Scripts

### `stop_multi_agent_system.sh`
- ✅ Parada elegante com SIGTERM
- ✅ Timeout de 10 segundos por processo
- ✅ Force kill se necessário
- ✅ Limpeza de processos órfãos
- ✅ Remoção de arquivos temporários
- ✅ Verificação de finalização

### `check_multi_agent_status.sh`
- ✅ Status de processos core
- ✅ Verificação de portas de rede
- ✅ Análise de logs (erros recentes)
- ✅ Configuração e arquivos
- ✅ Recursos do sistema
- ✅ Conectividade (Binance API)
- ✅ Resumo visual colorido

### `manage_multi_agent.sh`
- ✅ Interface unificada
- ✅ Menu interativo ou linha de comando
- ✅ Validação de diretório
- ✅ Integração com todos os scripts
- ✅ Múltiplas opções de inicialização
- ✅ Sistema de help completo

## 🎯 Estados do Sistema

### ✅ FULLY OPERATIONAL
- Multi-Agent Bot: RUNNING
- Flask API: RUNNING
- Portas ativas: 5000
- Logs sem erros críticos

### ⚠️ PARTIALLY OPERATIONAL
- Apenas um componente rodando
- Pode ser intencional (só bot ou só API)

### ❌ SYSTEM STOPPED
- Nenhum processo core ativo
- Estado após execução do stop

## 📁 Estrutura de Arquivos

```
binance-grid-bot-RL/
├── manage_multi_agent.sh          # 🎯 Script principal
├── stop_multi_agent_system.sh     # 🛑 Parada elegante
├── check_multi_agent_status.sh    # 📊 Verificação status
├── start_multi_agent_bot.sh       # 🚀 Iniciar bot
├── start_complete_system.sh       # 🚀 Sistema completo
├── monitor_bot.sh                 # 👁️ Monitoramento
├── logs/                          # 📋 Logs do sistema
│   ├── multi_agent_bot.log
│   ├── flask_api.log
│   └── trading.log
└── src/
    ├── multi_agent_bot.py         # 🤖 Bot principal
    └── main.py                    # 🌐 API Flask
```

## 🔧 Comandos de Verificação Rápida

```bash
# Verificar processos ativos
ps aux | grep -E "(multi_agent|main.py)" | grep -v grep

# Verificar portas em uso
lsof -Pi :5000 -sTCP:LISTEN

# Verificar logs recentes
tail -f logs/*.log

# Uso de memória dos processos
ps aux | grep multi_agent | awk '{print $6}' | paste -sd+ | bc
```

## 🚨 Resolução de Problemas

### Processos não param
```bash
# Force kill específico
pkill -9 -f multi_agent_bot.py

# Kill all Python processes (CUIDADO!)
pkill python3

# Verificar processos órfãos
ps aux | grep defunct
```

### Sistema não inicia
```bash
# Verificar dependências
./manage_multi_agent.sh health

# Verificar configuração
ls -la src/config/config.yaml
ls -la secrets/.env

# Verificar logs de startup
tail -n 50 system_startup.log
tail -n 50 bot_startup.log
```

### Performance Issues
```bash
# Verificar recursos
./check_multi_agent_status.sh

# Limpar cache
./manage_multi_agent.sh cleanup

# Restart clean
./manage_multi_agent.sh restart
```

## 🎮 Comandos de Uso Diário

```bash
# Manhã - verificar se está tudo rodando
./manage_multi_agent.sh health

# Iniciar sistema para o dia
./manage_multi_agent.sh start

# Monitorar durante o dia
./manage_multi_agent.sh monitor

# Verificar logs se necessário
./manage_multi_agent.sh logs

# Final do dia - parar sistema
./manage_multi_agent.sh stop

# Limpeza semanal
./manage_multi_agent.sh cleanup
```

## 📈 Melhorias Implementadas

1. **✅ Parada Elegante**: Sistema de shutdown que respeita os ciclos dos agentes
2. **✅ Verificação Completa**: Status detalhado de todos os componentes
3. **✅ Interface Unificada**: Um script para gerenciar tudo
4. **✅ Monitoramento Real**: Acompanhamento em tempo real
5. **✅ Limpeza Automática**: Remoção de arquivos temporários
6. **✅ Health Checks**: Verificações rápidas de saúde
7. **✅ Logs Centralizados**: Acesso fácil a todos os logs
8. **✅ Documentação Completa**: Guias para todas as situações

## 🔮 Próximos Passos Sugeridos

1. **Agendamento Automático**: Integrar com cron para start/stop automático
2. **Alertas por Email/Telegram**: Notificações de problemas
3. **Dashboard Web**: Interface web para monitoramento
4. **Backup Automático**: Backup de configurações e estados
5. **Métricas Avançadas**: Coleta e análise de performance
6. **Auto-recovery**: Restart automático em caso de falhas
7. **Load Balancing**: Distribuição de carga entre workers
8. **Containerização**: Docker para facilitar deployment

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Execute `./manage_multi_agent.sh health` primeiro
2. Verifique os logs com `./manage_multi_agent.sh logs`
3. Consulte este documento
4. Use `./manage_multi_agent.sh help` para comandos

**Status Atual**: ✅ **SISTEMA FINALIZADO E OPERACIONAL**

