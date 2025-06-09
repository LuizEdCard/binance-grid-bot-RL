# 🧪 Guia do Modo Shadow (Testnet)

O Modo Shadow agora utiliza o **Binance Testnet** para testes seguros sem risco financeiro real.

## 🎯 O que é o Modo Shadow

### Antes (Sistema Anterior)
- **Simulação local**: Dados reais, mas ordens simuladas
- **Sem execução real**: Apenas logs das operações
- **Dados de produção**: Usava API de produção para dados

### Agora (Novo Sistema)
- **Testnet real**: Conecta ao ambiente de teste da Binance
- **Execução real no testnet**: Ordens reais com dinheiro fictício
- **Ambiente isolado**: Completamente separado da produção
- **Teste completo**: Todos os fluxos funcionam como produção

## 🔧 Configuração

### 1. **Credenciais de API**

Crie/edite o arquivo `config/.env`:

```bash
# Produção (obrigatório)
BINANCE_API_KEY=sua_chave_de_producao
BINANCE_API_SECRET=seu_secret_de_producao

# Testnet (opcional - se não fornecida, usa credenciais de produção)
BINANCE_TESTNET_API_KEY=sua_chave_de_testnet
BINANCE_TESTNET_API_SECRET=seu_secret_de_testnet
```

### 2. **Obtendo Credenciais de Testnet**

#### Para Futures Testnet:
1. Acesse: https://testnet.binancefuture.com/
2. Faça login com sua conta Binance
3. Vá em **API Management**
4. Crie uma nova API Key para testnet
5. Anote a Key e Secret

#### Para Spot Testnet:
1. Acesse: https://testnet.binance.vision/
2. Faça login com sua conta Binance
3. Vá em **API Management** 
4. Crie uma nova API Key para testnet
5. Anote a Key e Secret

### 3. **Configuração do Bot**

```yaml
# config/config.yaml
operation_mode: Shadow  # Usa testnet
# ou
operation_mode: Production  # Usa produção
```

## 🚀 Como Usar

### 1. **Iniciar em Modo Shadow**
```bash
# Usando script (recomendado)
./start_multi_agent_bot.sh --shadow

# Ou diretamente
python src/multi_agent_bot.py
# (com operation_mode: Shadow no config.yaml)
```

### 2. **Verificar Conexão**
```bash
# Testar conectividade
python test_shadow_and_ai_fallback.py
```

### 3. **Logs de Verificação**
```
[INFO] APIClient inicializado no modo SHADOW (TESTNET)
[INFO] Tentando conectar à Testnet da Binance...
[INFO] Conectado com sucesso à Testnet da Binance
```

## 📊 Diferenças Entre Modos

| Aspecto | Shadow Mode | Production Mode |
|---------|-------------|-----------------|
| **Conexão** | Binance Testnet | Binance Production |
| **Dinheiro** | Fictício | Real |
| **Ordens** | Reais no testnet | Reais na produção |
| **Dados** | Reais do testnet | Reais da produção |
| **Risco** | Zero | Total |
| **Performance** | Idêntica | Idêntica |

## 🛡️ Segurança

### Vantagens do Novo Shadow Mode
- **Zero risco financeiro**: Dinheiro fictício
- **Teste completo**: Todos os fluxos de execução
- **Dados realistas**: Comportamento similar à produção
- **Depuração segura**: Pode testar qualquer estratégia

### Isolamento
- **Credenciais separadas**: Testnet e produção isolados
- **Ambiente isolado**: Nenhum impacto na produção
- **Rollback seguro**: Pode resetar conta testnet

## 🧪 Casos de Uso

### 1. **Desenvolvimento**
```bash
# Testar novas funcionalidades
./start_multi_agent_bot.sh --shadow --debug
```

### 2. **Validação de Estratégias**
```bash
# Rodar por 24h em testnet
./start_multi_agent_bot.sh --shadow
# Analisar logs e performance
```

### 3. **Teste de IA**
```bash
# Testar integração da IA sem risco
python test_ai_integration.py
./start_multi_agent_bot.sh --shadow
```

### 4. **Treinamento de Usuários**
```bash
# Ambiente seguro para aprender
./start_multi_agent_bot.sh --shadow
```

## 🔍 Troubleshooting

### Problemas Comuns

**"Failed to connect to testnet"**
```bash
# Verificar credenciais
curl -X GET 'https://testnet.binancefuture.com/fapi/v1/ping'

# Verificar chaves de API
python test_shadow_and_ai_fallback.py
```

**"Invalid API key"**
- Verificar se as credenciais são de testnet
- Confirmar se o testnet está habilitado na conta
- Verificar se as credenciais estão corretas no .env

**"Testnet data seems limited"**
- Normal - testnet pode ter menos pares disponíveis
- Testnet pode ter volumes menores
- Alguns indicadores podem ser diferentes

### Verificações
```bash
# 1. Testar conectividade básica
curl https://testnet.binancefuture.com/fapi/v1/ping

# 2. Testar com suas credenciais
python test_shadow_and_ai_fallback.py

# 3. Verificar logs detalhados
tail -f logs/multi_agent_bot.log | grep -i testnet
```

## 📈 Validação de Resultados

### Métricas do Testnet
- **Trades executados**: Ordens reais processadas
- **PnL calculado**: Baseado em preços reais
- **Performance**: Idêntica ao comportamento de produção
- **Latência**: Similar à produção

### Comparação
```python
# Comparar resultados testnet vs produção
testnet_results = analyze_testnet_performance()
production_results = analyze_production_performance()
correlation = calculate_correlation(testnet_results, production_results)
```

## 🎯 Migração para Produção

### Checklist Pré-Produção
- [ ] ✅ Testado extensivamente em Shadow mode
- [ ] ✅ Performance satisfatória por pelo menos 7 dias
- [ ] ✅ Todos os componentes funcionando
- [ ] ✅ Risk management validado
- [ ] ✅ Alertas configurados
- [ ] ✅ Monitoramento ativo

### Processo de Migração
```bash
# 1. Último teste em shadow
./start_multi_agent_bot.sh --shadow
# Verificar se tudo está OK

# 2. Fazer backup das configurações
cp -r config/ config_backup/

# 3. Migrar para produção
./start_multi_agent_bot.sh --production
```

## 💡 Dicas Importantes

### ⚠️ **Limitações do Testnet**
- Volumes podem ser menores que produção
- Alguns pares podem não estar disponíveis
- Latência pode ser ligeiramente diferente
- Dados podem ter pequenas variações

### ✅ **Boas Práticas**
- Sempre testar em Shadow antes da produção
- Manter credenciais testnet/produção separadas
- Documentar resultados dos testes
- Validar por períodos prolongados

### 🔄 **Workflow Recomendado**
1. **Desenvolvimento** → Shadow Mode
2. **Testes** → Shadow Mode (7+ dias)
3. **Validação** → Shadow Mode com volume real
4. **Produção** → Production Mode
5. **Monitoramento** → Comparação contínua

O Modo Shadow agora oferece um ambiente de teste **100% seguro e realista** para validar suas estratégias! 🚀