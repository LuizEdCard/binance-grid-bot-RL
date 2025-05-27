# Guia de Instalação da Biblioteca TA-Lib

Este guia explica como instalar a biblioteca TA-Lib no seu computador local. A TA-Lib é uma ferramenta poderosa para análise técnica, mas sua instalação pode ser um pouco mais complexa que outras bibliotecas Python, pois ela depende de uma base de código em linguagem C.

Siga as instruções correspondentes ao seu sistema operacional (Windows ou Linux).

**Importante:** Você precisará executar estes comandos no terminal ou prompt de comando do seu sistema, **não** dentro do ambiente do VS Code diretamente, a menos que o terminal integrado do VS Code esteja configurado corretamente para o seu sistema.

## Instalação no Windows

A forma mais fácil de instalar a TA-Lib no Windows é usando os arquivos pré-compilados (wheels) fornecidos pela comunidade. Certifique-se de baixar o arquivo correto para a sua versão do Python (3.9, 3.10, 3.11, etc.) e a arquitetura do seu sistema (32 ou 64 bits).

1.  **Verifique sua versão do Python e arquitetura:**
    *   Abra o Prompt de Comando (cmd) ou PowerShell.
    *   Digite `python --version` e pressione Enter para ver a versão (ex: Python 3.11.4).
    *   Digite `python -c "import struct; print(struct.calcsize(\'P\') * 8)"` e pressione Enter. Isso mostrará `64` para 64 bits ou `32` para 32 bits.

2.  **Baixe o arquivo Wheel (.whl) da TA-Lib:**
    *   Vá para o site não oficial que compila muitas bibliotecas C para Windows: [https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib)
    *   Procure por "TA-Lib".
    *   Encontre o arquivo que corresponde à sua versão do Python e arquitetura. Por exemplo, se você tem Python 3.11 de 64 bits, procure por algo como `TA_Lib‑0.4.28‑cp311‑cp311‑win_amd64.whl`.
    *   Clique no link para baixar o arquivo `.whl` e salve-o em um local fácil de encontrar (por exemplo, na sua pasta de Downloads).

3.  **Instale o arquivo Wheel:**
    *   Abra o Prompt de Comando ou PowerShell **na pasta onde você salvou o arquivo `.whl`**. Você pode fazer isso navegando com o comando `cd` (ex: `cd Downloads`).
    *   Certifique-se de que tem a ferramenta `wheel` instalada no Python: `pip install wheel`
    *   Instale a TA-Lib usando o nome do arquivo baixado:
        ```bash
        pip install TA_Lib‑0.4.28‑cp311‑cp311‑win_amd64.whl 
        ```
        (Substitua `TA_Lib‑0.4.28‑cp311‑cp311‑win_amd64.whl` pelo nome exato do arquivo que você baixou).

4.  **Verifique a instalação:**
    *   Abra o Python no terminal (digite `python`) e tente importar a biblioteca:
        ```python
        import talib
        print("TA-Lib importada com sucesso!")
        exit()
        ```
    *   Se não houver erros, a instalação foi bem-sucedida.

## Instalação no Linux (Ubuntu/Debian)

No Linux, você precisa primeiro instalar a biblioteca C da TA-Lib e depois a biblioteca Python.

1.  **Instale as dependências da biblioteca C:**
    *   Abra o terminal.
    *   Atualize a lista de pacotes:
        ```bash
        sudo apt update
        ```
    *   Instale as ferramentas de compilação necessárias:
        ```bash
        sudo apt install -y build-essential wget
        ```

2.  **Baixe e compile a biblioteca C da TA-Lib:**
    *   Baixe o código fonte da TA-Lib (verifique no site oficial [http://ta-lib.org/](http://ta-lib.org/) pela versão mais recente, se necessário):
        ```bash
        wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
        ```
    *   Descompacte o arquivo:
        ```bash
        tar -xzf ta-lib-0.4.0-src.tar.gz
        ```
    *   Entre na pasta descompactada:
        ```bash
        cd ta-lib/
        ```
    *   Configure a compilação:
        ```bash
        ./configure --prefix=/usr
        ```
    *   Compile:
        ```bash
        make
        ```
    *   Instale no sistema:
        ```bash
        sudo make install
        ```
    *   Volte para a pasta anterior:
        ```bash
        cd ..
        ```

3.  **Instale a biblioteca Python TA-Lib:**
    *   Agora que a base C está instalada, use o `pip` para instalar o wrapper Python:
        ```bash
        pip install TA-Lib
        ```

4.  **Verifique a instalação:**
    *   Abra o Python no terminal (digite `python` ou `python3`) e tente importar a biblioteca:
        ```python
        import talib
        print("TA-Lib importada com sucesso!")
        exit()
        ```
    *   Se não houver erros, a instalação foi bem-sucedida.

## Próximos Passos

Após instalar a TA-Lib com sucesso no seu sistema, você poderá executar o backend do bot e o script de treinamento do RL sem problemas relacionados a esta biblioteca. Lembre-se de instalar a TA-Lib dentro do ambiente virtual (`venv`) que você criar para o projeto backend e para o ambiente de treinamento do RL, repetindo o passo `pip install TA-Lib` (passo 3 no Windows ou passo 3 no Linux) após ativar cada ambiente virtual.

