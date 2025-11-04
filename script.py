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

def eh_produto_relevante(nome_produto, url=None):
    """
    Verifica se o produto é relevante para o estudo (alimentos).
    Exclui produtos de limpeza, higiene, pet, etc.
    Retorna: (bool, tipo_produto)
    """
    if not nome_produto:
        return False, None
    
    nome_lower = nome_produto.lower()
    url_lower = url.lower() if url else ""
    
    # Palavras-chave que indicam produtos NÃO relevantes (excluir)
    excluir_palavras = [
        'detergente', 'sabão', 'sabonete', 'shampoo', 'condicionador',
        'desinfetante', 'limpa vidro', 'limpa banheiro', 'água sanitária',
        'amaciante', 'alvejante', 'multiuso', 'limpa tudo',
        'ração', 'petisco', 'areia sanitária', 'coleira',
        'fralda', 'absorvente', 'papel higiênico', 'papel toalha',
        'guardanapo', 'cotonete', 'algodão', 'saco de lixo',
        'pilha', 'bateria', 'lâmpada', 'vela', 'incenso',
        'ferramenta', 'parafuso', 'prego', 'tinta', 'cola',
        'remédio', 'medicamento', 'vitamina', 'suplemento'
    ]
    
    # Verifica se contém palavras de exclusão
    for palavra in excluir_palavras:
        if palavra in nome_lower:
            return False, None
    
    # Palavras-chave que indicam categorias relevantes
    # Hortifruti
    if any(p in nome_lower for p in ['fruta', 'verdura', 'legume', 'hortaliça', 'folha']):
        return True, 'Hortifruti'
    
    # Mercearia/Grãos
    if any(p in nome_lower for p in ['arroz', 'feijão', 'lentilha', 'grão', 'cereal', 'aveia', 'quinoa']):
        return True, 'Mercearia'
    
    # Laticínios
    if any(p in nome_lower for p in ['leite', 'queijo', 'iogurte', 'requeijão', 'manteiga', 'nata']):
        return True, 'Laticínios'
    
    # Carnes
    if any(p in nome_lower for p in ['carne', 'frango', 'peixe', 'porco', 'bovino', 'suíno']):
        return True, 'Carnes'
    
    # Padaria
    if any(p in nome_lower for p in ['pão', 'biscoito', 'bolacha', 'biscoito', 'torrada']):
        return True, 'Padaria'
    
    # Bebidas (apenas sucos naturais, água, etc.)
    if any(p in nome_lower for p in ['suco', 'água', 'refrigerante', 'bebida']):
        # Exclui bebidas alcoólicas se necessário
        if not any(p in nome_lower for p in ['cerveja', 'vinho', 'vodka', 'whisky', 'água sanitária']):
            return True, 'Bebidas'
    
    # Se não identificou categoria específica mas é alimento comum
    # Verifica se parece ser um alimento (tem palavras relacionadas a comida)
    alimento_palavras = ['açúcar', 'sal', 'óleo', 'azeite', 'vinagre', 'massas', 'macarrão', 
                        'farinha', 'trigo', 'milho', 'soja', 'castanha', 'amendoim', 'nozes']
    if any(p in nome_lower for p in alimento_palavras):
        return True, 'Mercearia'
    
    # Se veio de URL de categorias de alimentos, provavelmente é relevante
    categorias_alimentos = ['hortifruti', 'mercearia', 'padaria', 'laticinios', 'carnes', 'bebidas']
    if any(cat in url_lower for cat in categorias_alimentos):
        return True, 'Outros Alimentos'
    
    # Se não identificou, mas não tem palavras de exclusão, pode ser relevante
    # (mais conservador - pode incluir alguns produtos que não são alimentos)
    return True, 'Outros'

def determinar_categoria(nome_produto, veio_de_organicos, tipo_produto=None):
    """
    Determina se um produto é orgânico ou não.
    Regra: Se veio da URL de orgânicos OU tem "organico" no nome → Orgânico
    Caso contrário → Não Orgânico
    """
    nome_lower = nome_produto.lower()
    tem_organico_no_nome = 'organico' in nome_lower or 'orgânico' in nome_lower or 'organic' in nome_lower
    
    if veio_de_organicos or tem_organico_no_nome:
        return 'Orgânico'
    else:
        return 'Não Orgânico'

def coletar_todas_paginas(url_base, veio_de_organicos=False, filtrar_relevantes=True, tipo_secao=None):
    """
    Coleta produtos de todas as páginas disponíveis.
    Para quando não encontrar mais produtos ou der erro.
    
    Args:
        url_base: URL base para coletar
        veio_de_organicos: Se veio de uma URL de orgânicos
        filtrar_relevantes: Se True, filtra apenas produtos relevantes (alimentos)
        tipo_secao: Tipo de seção (ex: 'Hortifruti', 'Mercearia')
    
    Retorna lista de todos os produtos coletados com categoria.
    """
    todos_produtos = []
    pagina = 1
    produtos_filtrados_total = 0
    formato_pagina = None  # Detecta o formato correto de paginação na primeira página
    
    print(f"\n{'='*60}")
    categoria_label = "Orgânicos" if veio_de_organicos else "Não Orgânicos"
    tipo_label = f" - {tipo_secao}" if tipo_secao else ""
    print(f"Iniciando coleta de todas as páginas - {categoria_label}{tipo_label}")
    print(f"URL base: {url_base}")
    if filtrar_relevantes:
        print(f"⚠️  Filtro ativo: Apenas produtos relevantes (alimentos)")
    else:
        print(f"⚠️  FILTRO DESABILITADO: coletando todos os produtos")
    print(f"{'='*60}\n")
    
    while True:
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
                        f"{url_base}&from={((pagina-1)*50)}",  # Formato com offset
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
                            # Formato funciona, usa ele
                            url = url_teste
                            # Detecta qual padrão usar
                            if '&page=' in url_teste or '?page=' in url_teste:
                                formato_pagina = 'page'
                            elif '&_page=' in url_teste or '?_page=' in url_teste:
                                formato_pagina = '_page'
                            elif '&from=' in url_teste or '?from=' in url_teste:
                                formato_pagina = 'from'
                            print(f"   ✅ Formato de paginação detectado: {formato_pagina}")
                            break
                
                if formato_pagina is None:
                    # Se não detectou, usa formato padrão
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
                    # Fallback
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
        
        # Filtra produtos relevantes e adiciona metadados
        produtos_validos = []
        produtos_filtrados_pagina = 0
        
        for produto in produtos_pagina:
            nome = produto['nome_bruto']
            
            # Verifica se é relevante
            if filtrar_relevantes:
                eh_relevante, tipo_produto = eh_produto_relevante(nome, url)
                if not eh_relevante:
                    produtos_filtrados_pagina += 1
                    produtos_filtrados_total += 1
                    continue
                produto['tipo_produto'] = tipo_produto or tipo_secao or 'Outros'
            else:
                produto['tipo_produto'] = tipo_secao or 'Outros'
            
            # Adiciona categoria (orgânico/não orgânico)
            produto['categoria'] = determinar_categoria(nome, veio_de_organicos, produto.get('tipo_produto'))
            produto['url_origem'] = url
            
            produtos_validos.append(produto)
        
        # Adiciona produtos encontrados
        todos_produtos.extend(produtos_validos)
        print(f"   ✅ {len(produtos_validos)} produtos encontrados (Total: {len(todos_produtos)})")
        if produtos_filtrados_pagina > 0:
            print(f"   ⚠️  {produtos_filtrados_pagina} produtos filtrados nesta página (não relevantes)")
        print()
        
        pagina += 1
        
        # Delay para não sobrecarregar o servidor
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"Coleta concluída: {len(todos_produtos)} produtos em {pagina-1} páginas")
    if produtos_filtrados_total > 0:
        print(f"Total de produtos filtrados (não relevantes): {produtos_filtrados_total}")
    print(f"{'='*60}\n")
    
    return todos_produtos

def buscar_produtos_por_termo(termo_busca, veio_de_organicos=False):
    """
    Busca produtos por termo em todo o catálogo do site.
    Usa a funcionalidade de busca do site com o formato correto:
    https://www.zonasul.com.br/organico?_q={termo}&map=ft
    Retorna lista de produtos encontrados.
    """
    todos_produtos = []
    
    # Codifica o termo de busca para URL (trata acentos e espaços)
    termo_encoded = quote(termo_busca, safe='')
    
    # URL de busca do Zona Sul no formato correto
    # Formato: /organico?_q={termo}&map=ft
    url_busca = f'https://www.zonasul.com.br/organico?_q={termo_encoded}&map=ft'
    
    print(f"\n🔍 Buscando por termo: '{termo_busca}'")
    print(f"   URL: {url_busca}")
    
    # Verifica se a URL existe e tem produtos
    soup, status = buscar_pagina(url_busca, mostrar_log=False)
    
    if soup is not None and status == 200:
        # Verifica se encontrou produtos
        produtos_teste = extrair_produtos_jsonld(soup)
        if len(produtos_teste) > 0:
            print(f"   ✅ URL de busca acessível com produtos encontrados")
            produtos = coletar_todas_paginas(
                url_busca,
                veio_de_organicos=veio_de_organicos,
                filtrar_relevantes=True,  # FILTRO ATIVO: apenas produtos relevantes (alimentos)
                tipo_secao=f'Busca: {termo_busca}'
            )
            todos_produtos.extend(produtos)
            print(f"   📊 {len(produtos)} produtos encontrados para '{termo_busca}'")
        else:
            print(f"   ⚠️  URL acessível mas nenhum produto encontrado na primeira página")
    else:
        print(f"   ⚠️  Erro ao acessar URL de busca (status: {status})")
    
    return todos_produtos

def coletar_produtos_organicos_todas_secoes():
    """
    Coleta produtos orgânicos usando estratégia de busca global + categorias específicas.
    Estratégia:
    1. Busca global por termos: organico, orgânico, organic, organicos, orgânicos
    2. Busca em categorias específicas relevantes (hortifruti, mercearia, laticínios, etc.)
    FILTRO ATIVO: apenas produtos relevantes (alimentos)
    Retorna lista de produtos orgânicos encontrados.
    """
    todos_produtos = []
    
    print("=" * 60)
    print("COLETA DE PRODUTOS ORGÂNICOS")
    print("ESTRATÉGIA: Busca Global + Categorias Específicas (FILTRO ATIVO)")
    print("=" * 60)
    
    # ETAPA 1: Buscas globais por termos
    print("\n" + "=" * 60)
    print("ETAPA 1: BUSCAS GLOBAIS POR TERMOS")
    print("=" * 60)
    
    termos_busca = ['organico', 'orgânico', 'organic', 'organicos', 'orgânicos']
    
    total_buscas = 0
    for termo in termos_busca:
        produtos_busca = buscar_produtos_por_termo(termo, veio_de_organicos=True)
        todos_produtos.extend(produtos_busca)
        total_buscas += len(produtos_busca)
        
        # Delay entre buscas
        if termo != termos_busca[-1]:
            time.sleep(2)
    
    print(f"\n✅ Total de produtos encontrados nas buscas globais: {total_buscas}")
    
    # ETAPA 2: Busca em categorias específicas relevantes
    print("\n⏳ Aguardando antes de buscar em categorias específicas...\n")
    time.sleep(3)
    
    print("\n" + "=" * 60)
    print("ETAPA 2: BUSCA EM CATEGORIAS ESPECÍFICAS")
    print("=" * 60)
    
    # Categorias que podem ter produtos orgânicos (apenas alimentos)
    categorias_relevantes = [
        ('hortifruti', 'Hortifruti'),
        ('mercearia', 'Mercearia'),
        ('laticinios', 'Laticínios'),
        ('padaria', 'Padaria'),
        ('carnes', 'Carnes'),
        ('bebidas', 'Bebidas'),
        ('congelados', 'Congelados'),
        ('frios', 'Frios'),
    ]
    
    for categoria_slug, categoria_nome in categorias_relevantes:
        # URL da categoria orgânica
        url = f'https://www.zonasul.com.br/{categoria_slug}/organicos'
        
        print(f"\n🔍 Buscando em: {categoria_nome}")
        produtos = coletar_todas_paginas(
            url, 
            veio_de_organicos=True, 
            filtrar_relevantes=True,  # FILTRO ATIVO: apenas produtos relevantes
            tipo_secao=categoria_nome
        )
        
        if len(produtos) > 0:
            todos_produtos.extend(produtos)
            print(f"   ✅ {len(produtos)} produtos encontrados em {categoria_nome}")
        else:
            print(f"   ⚠️  Nenhum produto encontrado em {categoria_nome}")
        
        # Delay entre categorias
        if categoria_slug != categorias_relevantes[-1][0]:
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"TOTAL DE PRODUTOS ORGÂNICOS COLETADOS: {len(todos_produtos)}")
    print(f"{'='*60}\n")
    
    return todos_produtos

# COMENTADO: Busca de produtos não orgânicos desabilitada para testes
# def coletar_produtos_nao_organicos_todas_secoes():
#     """
#     Coleta produtos não orgânicos das mesmas categorias relevantes.
#     Apenas produtos que sejam alimentos (relevantes para o estudo).
#     Foca em produtos que também têm versões orgânicas para comparação.
#     Retorna lista de produtos não orgânicos encontrados.
#     """
#     todos_produtos = []
#     
#     print("=" * 60)
#     print("COLETA DE PRODUTOS NÃO ORGÂNICOS")
#     print("APENAS CATEGORIAS RELEVANTES (ALIMENTOS)")
#     print("=" * 60)
#     
#     # Mesmas categorias usadas para orgânicos (apenas alimentos)
#     categorias_relevantes = [
#         ('hortifruti', 'Hortifruti'),
#         ('mercearia', 'Mercearia'),
#         ('laticinios', 'Laticínios'),
#         ('padaria', 'Padaria'),
#         ('carnes', 'Carnes'),
#         ('bebidas', 'Bebidas'),
#         ('congelados', 'Congelados'),
#         ('frios', 'Frios'),
#     ]
#     
#     for categoria_slug, categoria_nome in categorias_relevantes:
#         # URL da categoria (não orgânica)
#         url = f'https://www.zonasul.com.br/{categoria_slug}'
#         
#         print(f"\n🔍 Buscando em: {categoria_nome}")
#         produtos = coletar_todas_paginas(
#             url, 
#             veio_de_organicos=False, 
#             filtrar_relevantes=False,  # DESABILITADO
#             tipo_secao=categoria_nome
#         )
#         
#         if len(produtos) > 0:
#             todos_produtos.extend(produtos)
#             print(f"   ✅ {len(produtos)} produtos encontrados em {categoria_nome}")
#         else:
#             print(f"   ⚠️  Nenhum produto encontrado em {categoria_nome}")
#         
#         # Delay entre categorias
#         if categoria_slug != categorias_relevantes[-1][0]:
#             time.sleep(2)
#     
#     print(f"\n{'='*60}")
#     print(f"TOTAL DE PRODUTOS NÃO ORGÂNICOS COLETADOS: {len(todos_produtos)}")
#     print(f"{'='*60}\n")
#     
#     return todos_produtos

def coletar_todas_categorias():
    """
    Coleta produtos orgânicos apenas (para testes).
    Busca não orgânicos está comentada.
    Retorna lista de produtos orgânicos encontrados.
    """
    todos_produtos = []
    
    print("=" * 60)
    print("COLETA DE PRODUTOS ORGÂNICOS (MODO TESTE)")
    print("FILTRO ATIVO - BUSCA NÃO ORGÂNICOS COMENTADA")
    print("=" * 60)
    
    # Coleta produtos orgânicos de todas as seções
    produtos_organicos = coletar_produtos_organicos_todas_secoes()
    todos_produtos.extend(produtos_organicos)
    
    # COMENTADO: Coleta de produtos não orgânicos
    # print("\n⏳ Aguardando antes de coletar não orgânicos...\n")
    # time.sleep(2)
    # 
    # produtos_nao_organicos = coletar_produtos_nao_organicos_todas_secoes()
    # todos_produtos.extend(produtos_nao_organicos)
    
    return todos_produtos

def processar_dados_para_planilha(produtos):
    """
    Processa os produtos coletados e formata para a planilha.
    Retorna uma lista de dicionários com as colunas: Nome, Quantidade, Unidade, Preço, Categoria, Tipo Produto
    """
    dados_planilha = []
    
    for produto in produtos:
        nome_bruto = produto['nome_bruto']
        preco = produto['preco_bruto']
        categoria = produto['categoria']
        tipo_produto = produto.get('tipo_produto', 'Outros')
        
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
            'Categoria': categoria,
            'Tipo Produto': tipo_produto
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
    
    # Ordena por categoria, tipo de produto e nome
    df = df.sort_values(['Categoria', 'Tipo Produto', 'Nome']).reset_index(drop=True)
    
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
    
    print("\n📈 Resumo por tipo de produto:")
    resumo_tipo = df['Tipo Produto'].value_counts()
    for tipo, count in resumo_tipo.items():
        print(f"   - {tipo}: {count}")
    
    print("\n📈 Resumo combinado (Categoria x Tipo):")
    resumo_combinado = df.groupby(['Categoria', 'Tipo Produto']).size().sort_values(ascending=False)
    for (categoria, tipo), count in resumo_combinado.items():
        print(f"   - {categoria} / {tipo}: {count}")
    
    # Resumo final dos arquivos gerados
    print("\n" + "=" * 60)
    print("ARQUIVOS GERADOS:")
    if excel_salvo:
        print(f"   ✅ {nome_arquivo}")
    if nome_csv:
        print(f"   ✅ {nome_csv}")
    print("=" * 60)

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
