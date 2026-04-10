#!/bin/bash

# Criar e ativar o ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instalar as dependências
python -m pip install --upgrade pip
python -m pip install docker textual

# Executar o programa
python ./src/main.py