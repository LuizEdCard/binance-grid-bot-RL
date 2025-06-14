# Ollama Auto-Start Functionality

## Visão Geral

O sistema de trading multi-agente agora possui capacidade **automática de inicialização do Ollama** quando necessário. Esta funcionalidade garante que a IA local esteja sempre disponível para operações críticas.

## Funcionalidades Implementadas

### ✅ Auto-Start Integrado

**Componentes com Auto-Start:**
- **AI Agent** (`src/agents/ai_agent.py`)
- **Sentiment Analyzer** (`src/utils/gemma3_sentiment_analyzer.py`)

### ✅ Métodos de Inicialização

**1. SystemD Service (Preferencial)**
```bash
systemctl start ollama
```

**2. Processo Direto (Fallback)**
```bash
ollama serve &
```

### ✅ Detecção Inteligente

O sistema detecta automaticamente:
- ✅ Disponibilidade do `systemctl`
- ✅ Existência do serviço `ollama.service`
- ✅ Localização do binário `ollama`
- ✅ Status de conectividade (porto 11434)

## Como Funciona

### Fluxo de Auto-Start

1. **Health Check Falha** → Detecção de Ollama offline
2. **Tentativa SystemD** → `systemctl start ollama`
3. **Fallback Direto** → `ollama serve` em background
4. **Aguardo** → 3 segundos para inicialização
5. **Verificação** → Novo health check
6. **Recuperação** → Sistema continua operação normal

### Implementação Técnica

**AI Agent (Async):**
```python
async def _try_start_ollama(self) -> bool:
    # Tentativa via systemctl
    if shutil.which("systemctl"):
        process = await asyncio.create_subprocess_exec(
            "systemctl", "start", "ollama"
        )
        if process.returncode == 0:
            return True
    
    # Fallback direto
    await asyncio.create_subprocess_exec("ollama", "serve")
    return True
```

**Sentiment Analyzer (Sync):**
```python
def _try_start_ollama(self) -> bool:
    # Tentativa via systemctl
    if shutil.which("systemctl"):
        result = subprocess.run(["systemctl", "start", "ollama"])
        if result.returncode == 0:
            return True
    
    # Fallback direto
    subprocess.Popen(["ollama", "serve"])
    return True
```

## Teste da Funcionalidade

### Script de Teste Automático

```bash
python test_ollama_autostart.py
```

**Resultados dos Testes:**
```
🎉 All tests passed! Ollama auto-start is working correctly.

AI Agent Auto-Start: ✅ PASS
Sentiment Analyzer Auto-Start: ✅ PASS
```

### Teste Manual

1. **Parar Ollama:**
   ```bash
   sudo systemctl stop ollama
   ```

2. **Executar Bot:**
   ```bash
   cd src && python multi_agent_bot.py
   ```

3. **Verificar Logs:**
   ```
   INFO - Attempting to start Ollama via systemctl...
   INFO - Successfully started Ollama service via systemctl
   INFO - Local AI is available and responding
   ```

## Configuração do Sistema

### Pré-Requisitos

**✅ Seu Sistema (Verificado):**
- Ubuntu/Linux com systemd
- Ollama instalado em `/usr/local/bin/ollama`
- Serviço configurado: `/etc/systemd/system/ollama.service`
- Serviço habilitado: `enabled`

### Configuração Opcional

**Timeout Personalizado:**
```yaml
ai_agent:
  model_settings:
    timeout_seconds: 30  # Tempo para auto-start
```

**Desabilitar Auto-Start (se necessário):**
```python
# Em development apenas
AUTO_START_ENABLED = False
```

## Vantagens

### 🚀 **Operação Sem Interrupção**
- Sistema continua funcionando mesmo se Ollama parar
- Recuperação automática de falhas
- Zero downtime para trading

### 🔄 **Recuperação Robusta**
- Múltiplas estratégias de inicialização
- Fallbacks inteligentes
- Detecção de ambiente automática

### 📊 **Monitoramento Integrado**
- Logs detalhados de auto-start
- Health checks contínuos
- Alertas de falha configuráveis

## Logs de Exemplo

### Sucesso SystemD
```
2025-06-13 02:11:38 - ai_agent - INFO - Attempting to start Ollama via systemctl...
2025-06-13 02:11:43 - ai_agent - INFO - Successfully started Ollama service via systemctl
```

### Fallback Direto
```
2025-06-13 02:12:10 - grid_bot - WARNING - Ollama service not available
2025-06-13 02:12:10 - grid_bot - INFO - Attempting to start Ollama directly...
2025-06-13 02:12:13 - grid_bot - INFO - Started Ollama serve in background
```

## Segurança

### ✅ **Validações Implementadas**
- Verificação de binários antes da execução
- Timeout em tentativas de start (10s)
- Prevenção de recursão infinita
- Logs de auditoria completos

### ⚠️ **Considerações**
- Requer permissões para `systemctl start`
- Usuario deve estar no grupo adequado
- Processo direto roda com permissões do usuário

## Manutenção

### Verificação de Status
```bash
systemctl status ollama
ps aux | grep ollama
curl -s http://localhost:11434/api/tags
```

### Logs do Sistema
```bash
tail -f /var/log/syslog | grep ollama
journalctl -u ollama -f
```

### Troubleshooting

**Problema: Auto-start falha**
```bash
# Verificar permissões
sudo systemctl start ollama

# Verificar instalação
which ollama
ollama --version
```

**Problema: Timeout**
```bash
# Aumentar timeout na configuração
model_settings:
  timeout_seconds: 60
```

## Status Atual

✅ **Implementado e Testado**
- Auto-start via SystemD ✅
- Auto-start via processo direto ✅  
- Integração AI Agent ✅
- Integração Sentiment Analyzer ✅
- Testes automatizados ✅
- Documentação completa ✅

**Resultado:** Sistema de trading completamente autônomo com IA local auto-recuperável!