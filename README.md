# Scraper Zona Sul - Hortifruti

Script Python para fazer scraping de produtos do hortifruti (orgânicos e não orgânicos) do site do Zona Sul e salvar em planilha.

## 📋 Requisitos

- Python 3.7 ou superior

## 🚀 Instalação

### Usando Makefile (Recomendado)

```bash
# Ver todos os comandos disponíveis
make help

# Configuração completa (cria venv e instala dependências)
make setup

# Ou apenas instalar dependências (se o venv já existir)
make install
```

### Instalação Manual

1. Instale as dependências necessárias:

```bash
pip install -r requirements.txt
```

Ou instale manualmente:

```bash
pip install requests beautifulsoup4 pandas openpyxl lxml
```

## 💻 Como usar

### Usando Makefile (Recomendado)

```bash
# Executa o script de scraping
make run
```

### Execução Manual

```bash
# Se estiver usando ambiente virtual
source venv/bin/activate
python script.py

# Ou diretamente (se as dependências estiverem instaladas globalmente)
python script.py
```

O script irá:
1. Coletar todos os produtos orgânicos do hortifruti
2. Coletar todos os produtos não orgânicos do hortifruti
3. Salvar os dados em uma planilha Excel (`produtos_hortifruti_zonasul.xlsx`)

## 📊 Dados coletados

O script coleta as seguintes informações de cada produto:
- **Nome**: Nome do produto
- **Preço**: Preço do produto
- **Unidade**: Unidade de medida (kg, g, etc)
- **Categoria**: Orgânico ou Não Orgânico
- **É Orgânico**: Sim ou Não

## 🔧 Personalização

Você pode ajustar o script editando:
- `max_paginas`: Número máximo de páginas a processar (padrão: 50)
- `URL_BASE_ORGANICOS`: URL dos produtos orgânicos
- `URL_BASE_HORTIFRUTI`: URL do hortifruti geral
- Delays entre requisições (atualmente 2 segundos)

## ⚠️ Notas importantes

- O script inclui delays para não sobrecarregar o servidor
- Se o site mudar sua estrutura HTML, pode ser necessário ajustar os seletores
- O script tenta diferentes métodos para encontrar produtos, aumentando a robustez
- Se não conseguir salvar em Excel, salvará automaticamente em CSV

## 🛠️ Comandos Makefile

| Comando | Descrição |
|---------|-----------|
| `make help` | Mostra todos os comandos disponíveis |
| `make setup` | Configuração completa (cria venv e instala dependências) |
| `make install` | Instala as dependências |
| `make run` | Executa o script de scraping |
| `make test` | Testa se as dependências estão instaladas |
| `make clean-data` | Remove apenas os arquivos de dados gerados |
| `make clean` | Remove todos os arquivos gerados e o ambiente virtual |

## 🐛 Resolução de problemas

Se o script não encontrar produtos:
1. Verifique se o site está acessível
2. Inspecione o HTML do site para ver se a estrutura mudou
3. Ajuste os seletores CSS na função `extrair_produtos_da_pagina`

### Problemas com dependências

Se encontrar erros de módulos não encontrados:
```bash
# Usando Makefile
make install

# Ou manualmente
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

