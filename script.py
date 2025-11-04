import requests
from bs4 import BeautifulSoup
import json
import time
import re
import pandas as pd

# Configurações básicas
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

def separar_nome_quantidade(nome_bruto):
    """
    Separa o nome do produto da quantidade.
    Procura por padrões como: 180g, 600g, 1kg, 500ml, Com 10 Unidades, etc.
    Retorna: (nome_limpo, quantidade, unidade)
    Se não encontrar quantidade: (nome_limpo, "-", "-")
    """
    if not nome_bruto:
        return ("-", "-", "-")
    
    # Padrão 1: número seguido de unidade no final (180g, 600g, 1kg, 500ml, etc)
    padrao_final = r'(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l)\s*$'
    
    # Padrão 2: "Com X Unidades" ou "X Unidades" no final
    padrao_unidades = r'(?:com\s+)?(\d+(?:[.,]\d+)?)\s*(unidades?|un\.?)\s*$'
    
    # Tenta padrão final primeiro (mais comum)
    match = re.search(padrao_final, nome_bruto, re.IGNORECASE)
    
    if not match:
        # Tenta padrão de unidades
        match = re.search(padrao_unidades, nome_bruto, re.IGNORECASE)
    
    if match:
        # Encontrou quantidade
        quantidade = match.group(1)
        unidade = match.group(2).lower()
        
        # Remove a quantidade do nome (incluindo "Com" se existir)
        nome_limpo = nome_bruto[:match.start()].strip()
        # Remove "Com" se ficou no final do nome
        nome_limpo = re.sub(r'\s+[Cc]om\s*$', '', nome_limpo).strip()
        
        return (nome_limpo, quantidade, unidade)
    else:
        # Não encontrou quantidade
        return (nome_bruto.strip(), "-", "-")

def buscar_pagina(url, mostrar_log=False):
    """Faz a requisição e retorna o BeautifulSoup"""
    try:
        if mostrar_log:
            print(f"Acessando: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser'), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar {url}: {e}")
        return None, None

def extrair_produtos_jsonld(soup):
    """Extrai produtos do JSON-LD estruturado"""
    produtos = []
    
    # Procura scripts JSON-LD
    scripts = soup.find_all('script', type='application/ld+json')
    
    for script in scripts:
        try:
            data = json.loads(script.string)
            
            # Verifica se é uma lista de produtos
            if data.get('@type') == 'ItemList' and 'itemListElement' in data:
                for item in data['itemListElement']:
                    produto_item = item.get('item', {})
                    
                    if produto_item.get('@type') == 'Product':
                        nome = produto_item.get('name', '')
                        preco_info = produto_item.get('offers', {})
                        
                        # Tenta pegar o preço
                        preco = None
                        if isinstance(preco_info, dict):
                            preco = preco_info.get('price') or preco_info.get('lowPrice')
                        
                        if nome:
                            produtos.append({
                                'nome_bruto': nome,
                                'preco_bruto': preco
                            })
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"Erro ao processar JSON-LD: {e}")
            continue
    
    return produtos

def determinar_categoria(nome_produto, veio_de_organicos):
    """
    Determina se um produto é orgânico ou não.
    Regra: Se veio da URL de orgânicos OU tem "organico" no nome → Orgânico
    Caso contrário → Não Orgânico
    """
    nome_lower = nome_produto.lower()
    tem_organico_no_nome = 'organico' in nome_lower or 'orgânico' in nome_lower
    
    if veio_de_organicos or tem_organico_no_nome:
        return 'Orgânico'
    else:
        return 'Não Orgânico'

def coletar_todas_paginas(url_base, veio_de_organicos=False):
    """
    Coleta produtos de todas as páginas disponíveis.
    Para quando não encontrar mais produtos ou der erro.
    Retorna lista de todos os produtos coletados com categoria.
    """
    todos_produtos = []
    pagina = 1
    
    print(f"\n{'='*60}")
    categoria_label = "Orgânicos" if veio_de_organicos else "Não Orgânicos"
    print(f"Iniciando coleta de todas as páginas - {categoria_label}")
    print(f"URL base: {url_base}")
    print(f"{'='*60}\n")
    
    while True:
        # Monta URL da página
        if pagina == 1:
            url = url_base
        else:
            # Adiciona parâmetro de página
            if '?' in url_base:
                url = f"{url_base}&page={pagina}"
            else:
                url = f"{url_base}?page={pagina}"
        
        print(f"📄 Página {pagina}: {url}")
        
        # Busca a página
        soup, status = buscar_pagina(url)
        
        # Se deu erro ao buscar, para
        if soup is None or status != 200:
            print(f"❌ Erro ou página não encontrada. Parando na página {pagina}")
            break
        
        # Extrai produtos da página
        produtos_pagina = extrair_produtos_jsonld(soup)
        
        # Se não encontrou produtos, acabaram as páginas
        if len(produtos_pagina) == 0:
            print(f"✅ Fim das páginas (página {pagina} não tem produtos)")
            break
        
        # Adiciona categoria a cada produto
        for produto in produtos_pagina:
            produto['categoria'] = determinar_categoria(produto['nome_bruto'], veio_de_organicos)
        
        # Adiciona produtos encontrados
        todos_produtos.extend(produtos_pagina)
        print(f"   ✅ {len(produtos_pagina)} produtos encontrados (Total: {len(todos_produtos)})\n")
        
        pagina += 1
        
        # Delay para não sobrecarregar o servidor
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"Coleta concluída: {len(todos_produtos)} produtos em {pagina-1} páginas")
    print(f"{'='*60}\n")
    
    return todos_produtos

def coletar_todas_categorias():
    """
    Coleta produtos de ambas as categorias: orgânicos e não orgânicos.
    Retorna lista completa com todos os produtos.
    """
    todos_produtos = []
    
    # URLs
    url_organicos = 'https://www.zonasul.com.br/hortifruti/organicos'
    url_nao_organicos = 'https://www.zonasul.com.br/hortifruti'
    
    print("=" * 60)
    print("COLETA COMPLETA - ORGÂNICOS E NÃO ORGÂNICOS")
    print("=" * 60)
    
    # Coleta orgânicos
    produtos_organicos = coletar_todas_paginas(url_organicos, veio_de_organicos=True)
    todos_produtos.extend(produtos_organicos)
    
    # Delay entre categorias
    print("\n⏳ Aguardando antes de coletar não orgânicos...\n")
    time.sleep(2)
    
    # Coleta não orgânicos
    produtos_nao_organicos = coletar_todas_paginas(url_nao_organicos, veio_de_organicos=False)
    todos_produtos.extend(produtos_nao_organicos)
    
    return todos_produtos

def processar_dados_para_planilha(produtos):
    """
    Processa os produtos coletados e formata para a planilha.
    Retorna uma lista de dicionários com as colunas: Nome, Quantidade, Unidade, Preço, Categoria
    """
    dados_planilha = []
    
    for produto in produtos:
        nome_bruto = produto['nome_bruto']
        preco = produto['preco_bruto']
        categoria = produto['categoria']
        
        # Separa nome e quantidade
        nome_limpo, quantidade, unidade = separar_nome_quantidade(nome_bruto)
        
        # Formata preço
        if preco is None:
            preco_formatado = "-"
        else:
            # Garante que o preço seja um número
            try:
                preco_num = float(preco)
                preco_formatado = f"{preco_num:.2f}"
            except (ValueError, TypeError):
                preco_formatado = str(preco) if preco else "-"
        
        # Adiciona à lista
        dados_planilha.append({
            'Nome': nome_limpo,
            'Quantidade': quantidade,
            'Unidade': unidade,
            'Preço': preco_formatado,
            'Categoria': categoria
        })
    
    return dados_planilha

def salvar_planilha(produtos, nome_arquivo='produtos_hortifruti_zonasul.xlsx'):
    """
    Salva os produtos coletados em uma planilha Excel.
    Colunas: Nome, Quantidade, Unidade, Preço, Categoria
    """
    if not produtos:
        print("❌ Nenhum produto para salvar!")
        return
    
    print("\n" + "=" * 60)
    print("PROCESSANDO DADOS PARA PLANILHA")
    print("=" * 60)
    
    # Processa os dados
    dados_planilha = processar_dados_para_planilha(produtos)
    
    # Cria DataFrame
    df = pd.DataFrame(dados_planilha)
    
    # Remove duplicatas (baseado no nome)
    df_original = df.copy()
    df = df.drop_duplicates(subset=['Nome'], keep='first')
    
    if len(df) < len(df_original):
        print(f"⚠️  {len(df_original) - len(df)} produtos duplicados removidos")
    
    # Ordena por categoria e nome
    df = df.sort_values(['Categoria', 'Nome']).reset_index(drop=True)
    
    # Salva em Excel
    try:
        df.to_excel(nome_arquivo, index=False, engine='openpyxl')
        print(f"\n✅ Planilha salva com sucesso: {nome_arquivo}")
        print(f"📊 Total de produtos únicos: {len(df)}")
        
        # Mostra resumo
        print("\n📈 Resumo por categoria:")
        resumo = df['Categoria'].value_counts()
        for categoria, count in resumo.items():
            print(f"   - {categoria}: {count}")
        
    except ImportError:
        # Se openpyxl não estiver instalado, salva em CSV
        nome_csv = nome_arquivo.replace('.xlsx', '.csv')
        df.to_csv(nome_csv, index=False, encoding='utf-8-sig')
        print(f"\n✅ Planilha salva em CSV: {nome_csv}")
        print(f"📊 Total de produtos únicos: {len(df)}")
        print("💡 Para salvar em Excel, instale: pip install openpyxl")
        
        # Mostra resumo
        print("\n📈 Resumo por categoria:")
        resumo = df['Categoria'].value_counts()
        for categoria, count in resumo.items():
            print(f"   - {categoria}: {count}")
    except Exception as e:
        print(f"❌ Erro ao salvar planilha: {e}")
        # Tenta salvar em CSV como fallback
        nome_csv = nome_arquivo.replace('.xlsx', '.csv')
        try:
            df.to_csv(nome_csv, index=False, encoding='utf-8-sig')
            print(f"✅ Salvo em CSV como fallback: {nome_csv}")
        except Exception as e2:
            print(f"❌ Erro ao salvar CSV: {e2}")

def testar_categorias():
    """Testa a coleta e categorização"""
    produtos = coletar_todas_categorias()
    
    print("\n" + "=" * 60)
    print("RESUMO DA COLETA")
    print("=" * 60)
    print(f"Total de produtos coletados: {len(produtos)}")
    
    # Conta por categoria
    organicos = [p for p in produtos if p['categoria'] == 'Orgânico']
    nao_organicos = [p for p in produtos if p['categoria'] == 'Não Orgânico']
    
    print(f"  - Orgânicos: {len(organicos)}")
    print(f"  - Não Orgânicos: {len(nao_organicos)}")
    
    print("\nPrimeiros 10 produtos (com separação e categoria):")
    print("-" * 60)
    
    for i, produto in enumerate(produtos[:10], 1):
        nome_bruto = produto['nome_bruto']
        nome_limpo, quantidade, unidade = separar_nome_quantidade(nome_bruto)
        
        print(f"\n{i}. Nome: {nome_limpo}")
        print(f"   Quantidade: {quantidade} {unidade}")
        print(f"   Preço: R$ {produto['preco_bruto']}")
        print(f"   Categoria: {produto['categoria']}")
    
    # Salva na planilha
    salvar_planilha(produtos)
    
    return produtos

def main():
    """Função principal - executa coleta completa e salva planilha"""
    produtos = coletar_todas_categorias()
    
    print("\n" + "=" * 60)
    print("RESUMO DA COLETA")
    print("=" * 60)
    print(f"Total de produtos coletados: {len(produtos)}")
    
    # Conta por categoria
    organicos = [p for p in produtos if p['categoria'] == 'Orgânico']
    nao_organicos = [p for p in produtos if p['categoria'] == 'Não Orgânico']
    
    print(f"  - Orgânicos: {len(organicos)}")
    print(f"  - Não Orgânicos: {len(nao_organicos)}")
    
    # Salva na planilha
    salvar_planilha(produtos)
    
    return produtos

if __name__ == "__main__":
    produtos = main()
