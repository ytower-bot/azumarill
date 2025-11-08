import requests
from bs4 import BeautifulSoup
import json
import time
import re
import pandas as pd
from urllib.parse import quote

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

def classificar_tipo_produto(nome_produto):
    """
    Classifica o tipo do produto baseado no nome.
    Retorna: 'hortifruti', 'mercearia', 'frios e laticinios', 'carnes' ou 'processados'
    """
    if not nome_produto:
        return 'processados'
    
    nome_lower = nome_produto.lower()
    
    # Hortifruti: frutas, verduras, legumes, hortaliças
    palavras_hortifruti = [
        'fruta', 'verdura', 'legume', 'hortaliça', 'folha',
        'banana', 'maçã', 'laranja', 'tomate', 'cebola', 'alho',
        'batata', 'cenoura', 'abobrinha', 'berinjela', 'pimentão',
        'alface', 'rúcula', 'couve', 'repolho', 'brócolis',
        'morango', 'uva', 'mamão', 'abacate', 'limão',
        'chuchu', 'abóbora', 'quiabo', 'vagem', 'pepino'
    ]
    
    if any(palavra in nome_lower for palavra in palavras_hortifruti):
        return 'hortifruti'
    
    # Carnes: carnes, aves, peixes
    palavras_carnes = [
        'carne', 'frango', 'peixe', 'porco', 'bovino', 'suíno',
        'bife', 'alcatra', 'picanha', 'maminha', 'contra-filé',
        'coxinha', 'sobrecoxa', 'peito', 'salmão', 'tilápia',
        'sardinha', 'atum', 'linguiça', 'salsicha', 'embutido'
    ]
    
    if any(palavra in nome_lower for palavra in palavras_carnes):
        return 'carnes'
    
    # Frios e Laticínios: queijos, iogurtes, leites, requeijão, etc.
    palavras_frios_laticinios = [
        'queijo', 'iogurte', 'leite', 'requeijão', 'manteiga',
        'nata', 'creme de leite', 'ricota', 'cottage', 'mussarela',
        'presunto', 'mortadela', 'salame', 'peito de peru',
        'laticínio', 'laticinio'
    ]
    
    if any(palavra in nome_lower for palavra in palavras_frios_laticinios):
        return 'frios e laticinios'
    
    # Mercearia: grãos, cereais, farinhas, açúcares, óleos, etc.
    palavras_mercearia = [
        'arroz', 'feijão', 'lentilha', 'grão', 'cereal', 'aveia', 'quinoa',
        'farinha', 'trigo', 'milho', 'soja', 'castanha', 'amendoim', 'nozes',
        'açúcar', 'sal', 'óleo', 'azeite', 'vinagre', 'macarrão', 'massa',
        'biscoito', 'bolacha', 'café', 'chá', 'mel', 'geleia'
    ]
    
    if any(palavra in nome_lower for palavra in palavras_mercearia):
        return 'mercearia'
    
    # Processados: padaria, confeitaria, bebidas, condimentos, congelados, etc.
    # Se não se encaixou em nenhuma categoria acima, vai para processados
    return 'processados'

def coletar_todas_paginas(url_base, max_paginas=50):
    """
    Coleta produtos de todas as páginas disponíveis.
    Para quando não encontrar mais produtos ou der erro.
    Retorna lista de todos os produtos coletados.
    """
    todos_produtos = []
    pagina = 1
    formato_pagina = None
    urls_visitadas = set()  # Para evitar loops infinitos
    produtos_por_pagina = []  # Para detectar páginas repetidas
    
    print(f"\n{'='*60}")
    print(f"Iniciando coleta de todas as páginas")
    print(f"URL base: {url_base}")
    print(f"Limite máximo de páginas: {max_paginas}")
    print(f"{'='*60}\n")
    
    while pagina <= max_paginas:
        # Monta URL da página
        if pagina == 1:
            url = url_base
        else:
            # Detecta formato de paginação na página 2
            if pagina == 2 and formato_pagina is None:
                # Tenta diferentes formatos de paginação
                formatos_teste = []
                if '?' in url_base:
                    formatos_teste = [
                        f"{url_base}&page={pagina}",
                        f"{url_base}&_page={pagina}",
                        f"{url_base}&from={((pagina-1)*50)}",
                    ]
                else:
                    formatos_teste = [
                        f"{url_base}?page={pagina}",
                        f"{url_base}?_page={pagina}",
                        f"{url_base}?from={((pagina-1)*50)}",
                    ]
                
                # Testa cada formato
                for url_teste in formatos_teste:
                    soup_test, status_test = buscar_pagina(url_teste, mostrar_log=False)
                    if soup_test and status_test == 200:
                        produtos_test = extrair_produtos_jsonld(soup_test)
                        if len(produtos_test) > 0:
                            url = url_teste
                            if '&page=' in url_teste or '?page=' in url_teste:
                                formato_pagina = 'page'
                            elif '&_page=' in url_teste or '?_page=' in url_teste:
                                formato_pagina = '_page'
                            elif '&from=' in url_teste or '?from=' in url_teste:
                                formato_pagina = 'from'
                            print(f"   ✅ Formato de paginação detectado: {formato_pagina}")
                            break
                
                if formato_pagina is None:
                    formato_pagina = 'page'
                    if '?' in url_base:
                        url = f"{url_base}&page={pagina}"
                    else:
                        url = f"{url_base}?page={pagina}"
            else:
                # Usa o formato detectado
                if formato_pagina == 'page':
                    if '?' in url_base:
                        url = f"{url_base}&page={pagina}"
                    else:
                        url = f"{url_base}?page={pagina}"
                elif formato_pagina == '_page':
                    if '?' in url_base:
                        url = f"{url_base}&_page={pagina}"
                    else:
                        url = f"{url_base}?_page={pagina}"
                elif formato_pagina == 'from':
                    offset = (pagina - 1) * 50
                    if '?' in url_base:
                        url = f"{url_base}&from={offset}"
                    else:
                        url = f"{url_base}?from={offset}"
                else:
                    if '?' in url_base:
                        url = f"{url_base}&page={pagina}"
                    else:
                        url = f"{url_base}?page={pagina}"
        
        print(f"📄 Página {pagina}: {url}")
        
        # Verifica se já visitou esta URL (proteção contra loop)
        if url in urls_visitadas:
            print(f"⚠️  URL já visitada anteriormente. Parando para evitar loop infinito.")
            break
        urls_visitadas.add(url)
        
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
        
        # Verifica se esta página tem os mesmos produtos da anterior (proteção contra loop)
        if produtos_por_pagina and len(produtos_por_pagina) > 0:
            # Pega os nomes dos produtos da página anterior
            nomes_anterior = {p['nome_bruto'] for p in produtos_por_pagina[-1]}
            nomes_atual = {p['nome_bruto'] for p in produtos_pagina}
            
            # Se os produtos são exatamente iguais, pode ser loop
            if nomes_anterior == nomes_atual and len(nomes_anterior) > 0:
                print(f"⚠️  Página {pagina} tem os mesmos produtos da página anterior. Parando para evitar loop.")
                break
        
        # Guarda produtos desta página para comparação
        produtos_por_pagina.append(produtos_pagina.copy())
        
        # Adiciona categoria, tipo e metadados
        for produto in produtos_pagina:
            # A categoria será definida pela função que chama esta função
            if 'categoria' not in produto:
                produto['categoria'] = 'Não Orgânico'  # Padrão
            produto['tipo'] = classificar_tipo_produto(produto['nome_bruto'])
            produto['url_origem'] = url
        
        # Adiciona produtos encontrados
        todos_produtos.extend(produtos_pagina)
        print(f"   ✅ {len(produtos_pagina)} produtos encontrados (Total: {len(todos_produtos)})\n")
        
        pagina += 1
        
        # Delay para não sobrecarregar o servidor
        time.sleep(1)
    
    if pagina > max_paginas:
        print(f"⚠️  Limite máximo de {max_paginas} páginas atingido.")
    
    print(f"\n{'='*60}")
    print(f"Coleta concluída: {len(todos_produtos)} produtos em {pagina-1} páginas")
    print(f"{'='*60}\n")
    
    return todos_produtos

def buscar_produtos_por_termo(termo_busca):
    """
    Busca produtos orgânicos por termo usando o formato correto:
    https://www.zonasul.com.br/organico?_q={termo}&map=ft
    Retorna lista de produtos encontrados.
    """
    # Codifica o termo de busca para URL
    termo_encoded = quote(termo_busca, safe='')
    
    # URL de busca do Zona Sul no formato correto
    url_busca = f'https://www.zonasul.com.br/organico?_q={termo_encoded}&map=ft'
    
    print(f"\n🔍 Buscando por termo: '{termo_busca}'")
    print(f"   URL: {url_busca}")
    
    # Verifica se a URL existe e tem produtos
    soup, status = buscar_pagina(url_busca, mostrar_log=False)
    
    if soup is not None and status == 200:
        produtos_teste = extrair_produtos_jsonld(soup)
        if len(produtos_teste) > 0:
            print(f"   ✅ URL de busca acessível com produtos encontrados")
            produtos = coletar_todas_paginas(url_busca)
            print(f"   📊 {len(produtos)} produtos encontrados para '{termo_busca}'")
            return produtos
        else:
            print(f"   ⚠️  URL acessível mas nenhum produto encontrado na primeira página")
    else:
        print(f"   ⚠️  Erro ao acessar URL de busca (status: {status})")
    
    return []

def coletar_produtos_organicos():
    """
    Coleta produtos orgânicos fazendo busca global por termos.
    Termos buscados: orgânico, organico, organic
    Retorna lista de produtos orgânicos encontrados.
    """
    todos_produtos = []
    
    print("=" * 60)
    print("COLETA DE PRODUTOS ORGÂNICOS")
    print("ESTRATÉGIA: Busca Global por Termos")
    print("=" * 60)
    
    termos_busca = ['orgânico', 'organico', 'organic']
    
    for termo in termos_busca:
        produtos_busca = buscar_produtos_por_termo(termo)
        # Marca todos como orgânicos
        for produto in produtos_busca:
            produto['categoria'] = 'Orgânico'
        todos_produtos.extend(produtos_busca)
        
        # Delay entre buscas
        if termo != termos_busca[-1]:
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"TOTAL DE PRODUTOS ORGÂNICOS COLETADOS: {len(todos_produtos)}")
    print(f"{'='*60}\n")
    
    return todos_produtos

def coletar_produtos_nao_organicos():
    """
    Coleta produtos não orgânicos de categorias específicas de alimentos.
    Acessa páginas de categorias alimentares do site.
    Retorna lista de produtos não orgânicos encontrados.
    """
    todos_produtos = []
    
    print("=" * 60)
    print("COLETA DE PRODUTOS NÃO ORGÂNICOS")
    print("ESTRATÉGIA: Categorias de Alimentos")
    print("=" * 60)
    
    # Categorias de alimentos no Zona Sul
    categorias_alimentos = [
        ('hortifruti', 'Hortifruti'),
        ('mercearia', 'Mercearia'),
        ('laticinios', 'Laticínios'),
        ('carnes', 'Carnes'),
        ('padaria', 'Padaria'),
        ('bebidas', 'Bebidas'),
        ('congelados', 'Congelados'),
        ('frios', 'Frios'),
    ]
    
    for categoria_slug, categoria_nome in categorias_alimentos:
        # URL da categoria (sem /organicos)
        url = f'https://www.zonasul.com.br/{categoria_slug}'
        
        print(f"\n🔍 Coletando de: {categoria_nome}")
        print(f"   URL: {url}")
        
        produtos = coletar_todas_paginas(url)
        
        # Marca todos como não orgânicos
        for produto in produtos:
            produto['categoria'] = 'Não Orgânico'
        
        if len(produtos) > 0:
            todos_produtos.extend(produtos)
            print(f"   ✅ {len(produtos)} produtos encontrados em {categoria_nome}")
        else:
            print(f"   ⚠️  Nenhum produto encontrado em {categoria_nome}")
        
        # Delay entre categorias
        if categoria_slug != categorias_alimentos[-1][0]:
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"TOTAL DE PRODUTOS NÃO ORGÂNICOS COLETADOS: {len(todos_produtos)}")
    print(f"{'='*60}\n")
    
    return todos_produtos

def processar_dados_para_planilha(produtos):
    """
    Processa os produtos coletados e formata para a planilha.
    Retorna uma lista de dicionários com as colunas: Nome, Quantidade, Unidade, Preço, Categoria, Tipo
    """
    dados_planilha = []
    
    for produto in produtos:
        nome_bruto = produto['nome_bruto']
        preco = produto['preco_bruto']
        categoria = produto.get('categoria', 'Orgânico')
        tipo = produto.get('tipo', 'processados')
        
        # Separa nome e quantidade
        nome_limpo, quantidade, unidade = separar_nome_quantidade(nome_bruto)
        
        # Formata preço
        if preco is None:
            preco_formatado = "-"
        else:
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
            'Categoria': categoria,
            'Tipo': tipo
        })
    
    return dados_planilha

def salvar_planilha(produtos, nome_arquivo='produtos_hortifruti_zonasul.xlsx'):
    """
    Salva os produtos coletados em planilhas Excel e CSV.
    Colunas: Nome, Quantidade, Unidade, Preço, Categoria, Tipo Produto
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
    
    # Ordena por categoria, tipo e nome
    df = df.sort_values(['Categoria', 'Tipo', 'Nome']).reset_index(drop=True)
    
    # Gera nome do arquivo CSV
    nome_csv = nome_arquivo.replace('.xlsx', '.csv')
    
    # Salva em CSV (sempre)
    try:
        df.to_csv(nome_csv, index=False, encoding='utf-8-sig')
        print(f"\n✅ Planilha CSV salva com sucesso: {nome_csv}")
    except Exception as e:
        print(f"❌ Erro ao salvar CSV: {e}")
        nome_csv = None
    
    # Salva em Excel (se possível)
    excel_salvo = False
    try:
        df.to_excel(nome_arquivo, index=False, engine='openpyxl')
        print(f"✅ Planilha Excel salva com sucesso: {nome_arquivo}")
        excel_salvo = True
    except ImportError:
        print("⚠️  openpyxl não está instalado. CSV salvo, mas Excel não foi gerado.")
        print("💡 Para salvar em Excel, instale: pip install openpyxl")
    except Exception as e:
        print(f"⚠️  Erro ao salvar Excel: {e}")
        print("✅ CSV foi salvo com sucesso")
    
    # Mostra resumo
    print(f"\n📊 Total de produtos únicos: {len(df)}")
    
    print("\n📈 Resumo por categoria:")
    resumo = df['Categoria'].value_counts()
    for categoria, count in resumo.items():
        print(f"   - {categoria}: {count}")
    
    print("\n📈 Resumo por tipo:")
    resumo_tipo = df['Tipo'].value_counts()
    for tipo, count in resumo_tipo.items():
        print(f"   - {tipo}: {count}")
    
    # Resumo final dos arquivos gerados
    print("\n" + "=" * 60)
    print("ARQUIVOS GERADOS:")
    if excel_salvo:
        print(f"   ✅ {nome_arquivo}")
    if nome_csv:
        print(f"   ✅ {nome_csv}")
    print("=" * 60)

def main():
    """Função principal - executa coleta de produtos orgânicos e não orgânicos e salva planilha"""
    todos_produtos = []
    
    # Coleta produtos orgânicos
    produtos_organicos = coletar_produtos_organicos()
    todos_produtos.extend(produtos_organicos)
    
    # Delay entre coletas
    print("\n⏳ Aguardando antes de coletar produtos não orgânicos...\n")
    time.sleep(3)
    
    # Coleta produtos não orgânicos
    produtos_nao_organicos = coletar_produtos_nao_organicos()
    todos_produtos.extend(produtos_nao_organicos)
    
    print("\n" + "=" * 60)
    print("RESUMO DA COLETA COMPLETA")
    print("=" * 60)
    print(f"Total de produtos coletados: {len(todos_produtos)}")
    
    # Conta por categoria
    organicos = [p for p in todos_produtos if p.get('categoria') == 'Orgânico']
    nao_organicos = [p for p in todos_produtos if p.get('categoria') == 'Não Orgânico']
    
    print(f"  - Orgânicos: {len(organicos)}")
    print(f"  - Não Orgânicos: {len(nao_organicos)}")
    
    # Salva na planilha
    salvar_planilha(todos_produtos)
    
    return todos_produtos

if __name__ == "__main__":
    produtos = main()
