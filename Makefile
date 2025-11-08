.PHONY: help install run clean venv test

# Variáveis
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
SCRIPT = zonasul_scrapper.py
REQUIREMENTS = requirements.txt

# Cores para output
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m # No Color

help: ## Mostra esta mensagem de ajuda
	@echo "$(GREEN)Comandos disponíveis:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

venv: ## Cria o ambiente virtual
	@echo "$(GREEN)Criando ambiente virtual...$(NC)"
	@python3 -m venv $(VENV)
	@echo "$(GREEN)Ambiente virtual criado!$(NC)"

install: venv ## Instala as dependências
	@echo "$(GREEN)Instalando dependências...$(NC)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -r $(REQUIREMENTS)
	@echo "$(GREEN)Dependências instaladas!$(NC)"

run: ## Executa o script de scraping
	@echo "$(GREEN)Executando script de scraping...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Ambiente virtual não encontrado. Criando...$(NC)"; \
		$(MAKE) install; \
	fi
	@$(PYTHON) $(SCRIPT)

clean: ## Remove arquivos gerados e o ambiente virtual
	@echo "$(GREEN)Limpando arquivos...$(NC)"
	@rm -rf $(VENV)
	@rm -f produtos_hortifruti_zonasul.xlsx
	@rm -f produtos_hortifruti_zonasul.csv
	@rm -rf __pycache__
	@rm -rf .pytest_cache
	@rm -f *.pyc
	@echo "$(GREEN)Limpeza concluída!$(NC)"

clean-data: ## Remove apenas os arquivos de dados gerados (mantém venv)
	@echo "$(GREEN)Removendo arquivos de dados...$(NC)"
	@rm -f produtos_hortifruti_zonasul.xlsx
	@rm -f produtos_hortifruti_zonasul.csv
	@echo "$(GREEN)Arquivos de dados removidos!$(NC)"

test: ## Testa se as dependências estão instaladas
	@echo "$(GREEN)Testando dependências...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Ambiente virtual não encontrado. Execute 'make install' primeiro.$(NC)"; \
		exit 1; \
	fi
	@$(PYTHON) -c "import requests, bs4, pandas, openpyxl; print('$(GREEN)✓ Todas as dependências estão instaladas$(NC)')"

setup: install ## Configuração completa (cria venv e instala dependências)
	@echo "$(GREEN)Setup completo!$(NC)"

