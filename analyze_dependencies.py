#!/usr/bin/env python3
"""
Analisador de dependências - identifica quais bibliotecas são realmente usadas
"""

import os
import re
import ast
from collections import defaultdict, Counter
from pathlib import Path

def extract_imports_from_file(file_path):
    """Extrai todos os imports de um arquivo Python."""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse AST para imports seguros
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except:
            # Fallback para regex se AST falhar
            import_patterns = [
                r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
                r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import'
            ]
            
            for line in content.split('\n'):
                for pattern in import_patterns:
                    match = re.match(pattern, line.strip())
                    if match:
                        imports.add(match.group(1))
    
    except Exception as e:
        print(f"Erro lendo {file_path}: {e}")
    
    return imports

def analyze_project_dependencies():
    """Analisa todas as dependências usadas no projeto."""
    
    print("🔍 ANALISANDO DEPENDÊNCIAS DO PROJETO")
    print("=" * 60)
    
    # Diretórios para analisar
    source_dirs = ['src', '.']
    all_imports = Counter()
    file_count = 0
    
    # Padrões para filtrar arquivos Python
    python_files = []
    
    for source_dir in source_dirs:
        if os.path.exists(source_dir):
            for root, dirs, files in os.walk(source_dir):
                # Pular diretórios desnecessários
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env']]
                
                for file in files:
                    if file.endswith('.py') and not file.startswith('.'):
                        file_path = os.path.join(root, file)
                        python_files.append(file_path)
    
    print(f"📁 Analisando {len(python_files)} arquivos Python...")
    
    # Analisar cada arquivo
    for file_path in python_files:
        imports = extract_imports_from_file(file_path)
        all_imports.update(imports)
        file_count += 1
    
    print(f"✅ Análise concluída: {file_count} arquivos processados")
    
    return all_imports

def load_requirements():
    """Carrega requirements de ambos os arquivos."""
    requirements = {}
    
    req_files = ['requirements.txt', 'requirements_multi_agent.txt']
    
    for req_file in req_files:
        if os.path.exists(req_file):
            print(f"\n📦 Analisando {req_file}...")
            
            with open(req_file, 'r') as f:
                lines = f.readlines()
            
            current_reqs = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extrair nome da biblioteca
                    package_name = re.split(r'[>=<!=]', line)[0].strip()
                    current_reqs.append(package_name)
            
            requirements[req_file] = current_reqs
            print(f"   📋 {len(current_reqs)} dependências encontradas")
    
    return requirements

def categorize_imports(imports):
    """Categoriza imports entre built-in, third-party e locais."""
    
    # Módulos built-in do Python
    builtin_modules = {
        'sys', 'os', 'time', 'datetime', 'json', 'csv', 'sqlite3', 'urllib', 
        'http', 're', 'math', 'random', 'collections', 'itertools', 'functools',
        'typing', 'dataclasses', 'enum', 'abc', 'asyncio', 'logging', 'warnings',
        'pathlib', 'glob', 'shutil', 'tempfile', 'pickle', 'gzip', 'zipfile',
        'hashlib', 'hmac', 'base64', 'uuid', 'decimal', 'fractions', 'statistics',
        'threading', 'multiprocessing', 'concurrent', 'queue', 'socket', 'ssl'
    }
    
    # Módulos locais do projeto
    local_modules = {
        'utils', 'core', 'agents', 'integrations', 'routes', 'models', 'rl',
        'src', 'tests', 'config'
    }
    
    categorized = {
        'builtin': [],
        'third_party': [],
        'local': [],
        'unknown': []
    }
    
    for module, count in imports.most_common():
        if module in builtin_modules:
            categorized['builtin'].append((module, count))
        elif module in local_modules:
            categorized['local'].append((module, count))
        elif len(module) > 1:  # Filtrar imports de uma letra
            categorized['third_party'].append((module, count))
        else:
            categorized['unknown'].append((module, count))
    
    return categorized

def find_unused_dependencies():
    """Identifica dependências não utilizadas."""
    
    print("\n🔍 IDENTIFICANDO DEPENDÊNCIAS NÃO UTILIZADAS")
    print("=" * 60)
    
    # Analisar imports do projeto
    project_imports = analyze_project_dependencies()
    categorized_imports = categorize_imports(project_imports)
    
    # Carregar requirements
    requirements = load_requirements()
    
    # Mapear nomes de pacotes para imports
    package_mappings = {
        'python-binance': 'binance',
        'TA-Lib': 'talib',
        'pandas-ta': 'pandas_ta',
        'python-dotenv': 'dotenv',
        'python-telegram-bot': 'telegram',
        'stable-baselines3': 'stable_baselines3',
        'scikit-learn': 'sklearn',
        'flask-cors': 'flask_cors',
        'tensorflow-cpu': 'tensorflow',
        'asyncio-throttle': 'asyncio_throttle',
        'prometheus-client': 'prometheus_client',
        'memory-profiler': 'memory_profiler',
        'py-spy': 'py_spy'
    }
    
    used_third_party = {module for module, _ in categorized_imports['third_party']}
    
    print(f"\n📊 RESUMO DE IMPORTS:")
    print(f"   Built-in: {len(categorized_imports['builtin'])}")
    print(f"   Third-party: {len(categorized_imports['third_party'])}")
    print(f"   Local: {len(categorized_imports['local'])}")
    
    print(f"\n📦 THIRD-PARTY IMPORTS UTILIZADOS:")
    for module, count in categorized_imports['third_party']:
        print(f"   {module} (usado {count}x)")
    
    # Verificar cada arquivo de requirements
    for req_file, packages in requirements.items():
        print(f"\n❌ DEPENDÊNCIAS POSSIVELMENTE NÃO UTILIZADAS em {req_file}:")
        
        unused = []
        used = []
        unclear = []
        
        for package in packages:
            # Verificar se o pacote é usado
            import_name = package_mappings.get(package, package)
            
            if import_name in used_third_party:
                used.append(package)
            elif package in ['sqlite3']:  # Built-in
                used.append(package)
            elif package in ['pytest', 'pytest-asyncio', 'pytest-cov', 'black', 'flake8', 'mypy', 'py-spy', 'memory-profiler']:
                unclear.append(f"{package} (dev/testing)")
            elif package in ['redis', 'prometheus-client', 'matplotlib', 'plotly', 'tweepy']:
                unclear.append(f"{package} (opcional)")
            else:
                unused.append(package)
        
        for package in unused:
            print(f"   ❌ {package}")
        
        for package in unclear:
            print(f"   ⚠️ {package}")
        
        print(f"\n✅ DEPENDÊNCIAS EM USO em {req_file}: {len(used)}")
        for package in used[:10]:  # Mostrar apenas os primeiros 10
            print(f"   ✅ {package}")
        if len(used) > 10:
            print(f"   ... e mais {len(used) - 10}")

def create_optimized_requirements():
    """Cria um requirements.txt otimizado."""
    
    print(f"\n🔧 CRIANDO REQUIREMENTS OTIMIZADO...")
    
    # Dependências essenciais baseadas na análise
    essential_deps = [
        "# Core dependencies",
        "numpy>=1.21.0",
        "pandas>=1.3.0", 
        "pyyaml>=6.0",
        "",
        "# API and networking",
        "aiohttp>=3.8.0",
        "requests>=2.28.0",
        "python-binance>=1.0.15",
        "",
        "# Machine Learning (apenas se usado)", 
        "tensorflow-cpu==2.19.0",
        "scikit-learn>=1.1.0",
        "gymnasium>=1.1.1",
        "",
        "# Technical Analysis",
        "TA-Lib>=0.4.25  # Requires manual installation",
        "",
        "# System monitoring",
        "psutil>=5.9.0",
        "",
        "# Telegram notifications",
        "python-telegram-bot>=20.0",
        "",
        "# Optional: Development tools",
        "# pytest>=7.1.0",
        "# black>=22.0.0",
    ]
    
    optimized_file = "requirements_optimized.txt"
    
    with open(optimized_file, 'w') as f:
        f.write('\n'.join(essential_deps))
    
    print(f"✅ Requirements otimizado criado: {optimized_file}")
    
    return optimized_file

def main():
    print("🧹 ANÁLISE E LIMPEZA DE DEPENDÊNCIAS")
    print("=" * 70)
    
    find_unused_dependencies()
    optimized_file = create_optimized_requirements()
    
    print(f"\n💡 RECOMENDAÇÕES:")
    print(f"   1. Revisar dependências marcadas como ❌")
    print(f"   2. Considerar remover dependências opcionais não utilizadas")  
    print(f"   3. Usar {optimized_file} como base para novo requirements.txt")
    print(f"   4. Testar sistema após remoção de dependências")
    
    print(f"\n🔧 PRÓXIMOS PASSOS:")
    print(f"   pip uninstall <package_name>  # Para remover pacotes")
    print(f"   pip install -r {optimized_file}  # Para testar versão limpa")

if __name__ == "__main__":
    main()