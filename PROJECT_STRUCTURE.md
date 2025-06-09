# 📁 Estrutura do Projeto

Este projeto foi reorganizado para melhor organização dos arquivos:

## 📂 Estrutura de Pastas

```
binance-grid-bot-RL/
├── 📁 src/                    # Código fonte principal
│   ├── agents/               # Agentes especializados
│   ├── core/                 # Lógica de negociação
│   ├── utils/                # Utilitários e ferramentas
│   └── config/               # Configurações
├── 📁 docs/                   # Documentação
│   ├── README.md             # Documentação principal
│   ├── CLAUDE.md             # Instruções para Claude Code
│   ├── AI_INTEGRATION_GUIDE.md    # Guia de integração da IA
│   ├── SHADOW_MODE_GUIDE.md       # Guia do modo Shadow (testnet)
│   └── talib_installation_guide.md
├── 📁 tests/                  # Testes e diagnósticos
│   ├── test_*.py             # Scripts de teste
│   ├── quick_*.py            # Testes rápidos
│   └── diagnose*.py          # Scripts de diagnóstico
├── 📁 config/                 # Configurações globais
├── 📁 logs/                   # Logs do sistema
├── 📁 data/                   # Dados de mercado
└── 📁 models/                 # Modelos de ML/IA
```

## 🔗 Links Rápidos

### 📖 Documentação
- **Principal**: [`docs/README.md`](docs/README.md)
- **Instruções Claude Code**: [`docs/CLAUDE.md`](docs/CLAUDE.md)  
- **Integração da IA**: [`docs/AI_INTEGRATION_GUIDE.md`](docs/AI_INTEGRATION_GUIDE.md)
- **Modo Shadow**: [`docs/SHADOW_MODE_GUIDE.md`](docs/SHADOW_MODE_GUIDE.md)

### 🧪 Testes
- **Teste Rápido**: `python tests/quick_test.py`
- **Shadow + IA**: `python tests/test_shadow_and_ai_fallback.py`
- **Integração IA**: `python tests/test_ai_integration.py`

### 🚀 Comandos Principais
```bash
# Iniciar sistema multi-agente
python src/multi_agent_bot.py

# Iniciar API
python src/main.py

# Teste completo do ambiente
python tests/test_shadow_and_ai_fallback.py
```

## 🆕 Novidades

### ✅ Concluído
- **Modo Shadow** agora usa Binance Testnet (ambiente real de teste)
- **Fallback gracioso** quando IA está offline - bot continua operando
- **Arquitetura multi-agente** com agentes especializados
- **Integração de IA local** na porta 1234

### 📁 Reorganização
- Documentação movida para `docs/`
- Testes movidos para `tests/`
- Paths atualizados nos scripts

Consulte [`docs/README.md`](docs/README.md) para documentação completa!