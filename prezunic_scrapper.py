import requests
from bs4 import BeautifulSoup
import json
import time
import re
import pandas as pd
from urllib.parse import quote

# Configurações básicas
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def determinar_se_organico(nome_produto):
    """
    Determina se o produto é orgânico baseado no nome.
    Retorna: 'Orgânico' ou 'Não Orgânico'
    """
    if not nome_produto:
        return 'Não Orgânico'
    
    nome_lower = nome_produto.lower()
    
    # Procura por palavras relacionadas a orgânico
    palavras_organico = ['orgânico', 'organico', 'organic', 'bio', 'biológico', 'biologico']
    
    if any(palavra in nome_lower for palavra in palavras_organico):
        return 'Orgânico'
    
    return 'Não Orgânico'

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

def extrair_produtos_html(soup):
    """
    Extrai produtos diretamente do HTML.
    Procura por elementos comuns de produtos em sites de e-commerce.
    """
    produtos = []
    
    # Prezunic usa VTEX, então vamos procurar por classes comuns do VTEX
    # Classes comuns: vtex-product-summary-2-x-container, vtex-product-summary-2-x-nameContainer, etc.
    
    # Procura por containers de produtos
    containers_produto = soup.find_all(['div', 'article', 'section'], 
                                      class_=lambda x: x and ('product' in str(x).lower() or 
                                                             'summary' in str(x).lower() or
                                                             'item' in str(x).lower()))
    
    if len(containers_produto) == 0:
        # Tenta procurar por links de produtos
        links_produto = soup.find_all('a', href=re.compile(r'/produto|/p/|/product'))
        
        for link in links_produto:
            # Tenta encontrar o nome do produto próximo ao link
            container = link.find_parent(['div', 'article', 'section'])
            if container:
                # Procura por nome do produto
                nome_elem = container.find(['h2', 'h3', 'span', 'div'], 
                                          class_=lambda x: x and ('name' in str(x).lower() or 
                                                                 'title' in str(x).lower()))
                if not nome_elem:
                    nome_elem = link
                
                nome = nome_elem.get_text(strip=True) if nome_elem else link.get_text(strip=True)
                
                # Procura por preço
                preco_elem = container.find(['span', 'div', 'p'], 
                                           class_=lambda x: x and ('price' in str(x).lower() or 
                                                                   'valor' in str(x).lower()))
                preco = None
                if preco_elem:
                    preco_texto = preco_elem.get_text(strip=True)
                    # Extrai número do preço
                    match_preco = re.search(r'R\$\s*(\d+[.,]\d+)', preco_texto)
                    if match_preco:
                        preco = match_preco.group(1).replace(',', '.')
                
                if nome:
                    produtos.append({
                        'nome_bruto': nome,
                        'preco_bruto': preco
                    })
    
    # Se ainda não encontrou, tenta procurar por imagens de produtos (alt text geralmente tem o nome)
    if len(produtos) == 0:
        imagens_produto = soup.find_all('img', alt=True, 
                                       class_=lambda x: x and ('product' in str(x).lower() or 
                                                              'image' in str(x).lower()))
        
        for img in imagens_produto:
            nome = img.get('alt', '').strip()
            if nome and len(nome) > 5:  # Nome deve ter pelo menos alguns caracteres
                # Tenta encontrar preço próximo
                container = img.find_parent(['div', 'article', 'section'])
                preco = None
                if container:
                    preco_elem = container.find(['span', 'div', 'p'], 
                                               class_=lambda x: x and 'price' in str(x).lower())
                    if preco_elem:
                        preco_texto = preco_elem.get_text(strip=True)
                        match_preco = re.search(r'R\$\s*(\d+[.,]\d+)', preco_texto)
                        if match_preco:
                            preco = match_preco.group(1).replace(',', '.')
                
                produtos.append({
                    'nome_bruto': nome,
                    'preco_bruto': preco
                })
    
    return produtos

def extrair_produtos(soup):
    """
    Tenta extrair produtos usando diferentes métodos.
    Prioridade: JSON-LD > HTML
    """
    produtos = []
    
    # Primeiro tenta JSON-LD
    produtos = extrair_produtos_jsonld(soup)
    
    # Se não encontrou, tenta HTML
    if len(produtos) == 0:
        produtos = extrair_produtos_html(soup)
    
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
    return 'processados'

def coletar_todas_paginas(url_base, max_paginas=100, produtos_unicos_globais=None):
    """
    Coleta produtos de todas as páginas disponíveis.
    Para quando não encontrar mais produtos ou der erro.
    Retorna lista de todos os produtos coletados.
    """
    todos_produtos = []
    pagina = 1  # Prezunic começa na página 1
    urls_visitadas = set()
    
    # Usa conjunto global de produtos únicos se fornecido, senão cria um novo
    if produtos_unicos_globais is None:
        produtos_unicos = set()
    else:
        produtos_unicos = produtos_unicos_globais
    
    print(f"\n{'='*60}")
    print(f"Iniciando coleta de todas as páginas")
    print(f"URL base: {url_base}")
    print(f"Limite máximo de páginas: {max_paginas}")
    print(f"{'='*60}\n")
    
    while pagina <= max_paginas:
        # Monta URL da página
        # Prezunic usa formato: ?page=1, ?page=2, etc.
        if '?' in url_base:
            url = f"{url_base}&page={pagina}"
        else:
            url = f"{url_base}?page={pagina}"
        
        print(f"📄 Página {pagina}: {url}")
        
        # Verifica se já visitou esta URL
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
        produtos_pagina = extrair_produtos(soup)
        
        # Se não encontrou produtos, acabaram as páginas
        if len(produtos_pagina) == 0:
            print(f"✅ Fim das páginas (página {pagina} não tem produtos)")
            break
        
        # Remove duplicatas baseado no nome
        produtos_novos = []
        for produto in produtos_pagina:
            nome = produto.get('nome_bruto', '').strip().lower()
            if nome and nome not in produtos_unicos:
                produtos_unicos.add(nome)
                produtos_novos.append(produto)
        
        if len(produtos_novos) == 0:
            print(f"⚠️  Todos os produtos da página {pagina} são duplicados. Parando.")
            break
        
        # Adiciona tipo e metadados (NÃO marca categoria orgânico/não orgânico aqui)
        for produto in produtos_novos:
            produto['tipo'] = classificar_tipo_produto(produto['nome_bruto'])
            produto['url_origem'] = url
        
        # Adiciona produtos encontrados
        todos_produtos.extend(produtos_novos)
        print(f"   ✅ {len(produtos_novos)} produtos novos encontrados (Total nesta categoria: {len(todos_produtos)})\n")
        
        pagina += 1
        
        # Delay para não sobrecarregar o servidor
        time.sleep(1)
    
    if pagina > max_paginas:
        print(f"⚠️  Limite máximo de {max_paginas} páginas atingido.")
    
    print(f"\n{'='*60}")
    print(f"Coleta concluída: {len(todos_produtos)} produtos únicos em {pagina-1} páginas")
    print(f"{'='*60}\n")
    
    return todos_produtos

def processar_dados_para_planilha(produtos):
    """
    Processa os produtos coletados e formata para a planilha.
    AQUI é onde determinamos se é orgânico ou não baseado no nome.
    Retorna uma lista de dicionários com as colunas: Nome, Quantidade, Unidade, Preço, Categoria, Tipo
    """
    dados_planilha = []
    
    for produto in produtos:
        nome_bruto = produto['nome_bruto']
        preco = produto['preco_bruto']
        tipo = produto.get('tipo', 'processados')
        
        # AQUI determinamos se é orgânico baseado no nome
        categoria = determinar_se_organico(nome_bruto)
        
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

def salvar_planilha(produtos, nome_arquivo='produtos_hortifruti_prezunic.xlsx'):
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

def coletar_produtos_organicos():
    """
    Coleta produtos orgânicos fazendo busca por termo.
    Retorna lista de produtos orgânicos encontrados.
    """
    todos_produtos = []
    produtos_unicos_globais = set()  # Para evitar duplicatas entre diferentes buscas
    
    print("=" * 60)
    print("COLETA DE PRODUTOS ORGÂNICOS")
    print("ESTRATÉGIA: Busca por Termo 'organico'")
    print("=" * 60)
    
    url_busca = 'https://www.prezunic.com.br/organico?_q=organico&map=ft'
    
    print(f"\n🔍 Coletando produtos orgânicos")
    print(f"   URL: {url_busca}")
    
    # Coleta produtos orgânicos de todas as páginas
    produtos = coletar_todas_paginas(url_busca, max_paginas=100, 
                                     produtos_unicos_globais=produtos_unicos_globais)
    
    todos_produtos.extend(produtos)
    
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
    produtos_unicos_globais = set()  # Para evitar duplicatas entre categorias
    
    print("=" * 60)
    print("COLETA DE PRODUTOS NÃO ORGÂNICOS")
    print("ESTRATÉGIA: Categorias de Alimentos")
    print("=" * 60)
    
    # Categorias de alimentos no Prezunic (baseado no menu HTML fornecido)
    categorias_alimentos = [
        ('mercearia', 'Mercearia', 'https://www.prezunic.com.br/mercearia'),
        ('carnes-e-aves', 'Carnes e Aves', 'https://www.prezunic.com.br/carnes-e-aves'),
        ('frios-e-laticinios', 'Frios e Laticínios', 'https://www.prezunic.com.br/frios-e-laticinios'),
        ('hortifruti', 'Hortifruti', 'https://www.prezunic.com.br/hortifruti'),
    ]
    
    for categoria_slug, categoria_nome, url in categorias_alimentos:
        print(f"\n🔍 Coletando de: {categoria_nome}")
        print(f"   URL: {url}")
        
        produtos = coletar_todas_paginas(url, max_paginas=100,
                                         produtos_unicos_globais=produtos_unicos_globais)
        
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

def main():
    """Função principal - executa coleta de produtos orgânicos e não orgânicos e salva planilha"""
    todos_produtos = []
    
    # Primeiro, testa se consegue extrair produtos
    print("=" * 60)
    print("TESTE INICIAL - VERIFICANDO EXTRAÇÃO")
    print("=" * 60)
    
    url_teste = 'https://www.prezunic.com.br/organico?_q=organico&map=ft'
    soup, status = buscar_pagina(url_teste)
    
    if soup is None or status != 200:
        print("❌ Erro ao acessar a página. Verifique a URL e sua conexão.")
        return []
    
    # Testa extração
    produtos_teste = extrair_produtos(soup)
    
    if len(produtos_teste) == 0:
        print("⚠️  Nenhum produto encontrado na primeira página.")
        print("⚠️  O site pode estar usando JavaScript para carregar produtos dinamicamente.")
        print("⚠️  Será necessário usar Selenium ou outra ferramenta de renderização JavaScript.")
        return []
    
    print(f"✅ {len(produtos_teste)} produtos encontrados na primeira página!")
    print("✅ O site usa JSON-LD ou HTML para produtos. Continuando coleta...\n")
    
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
    
    print("(A categoria Orgânico/Não Orgânico será determinada no processamento)")
    
    # Salva na planilha (aqui determina se é orgânico ou não)
    salvar_planilha(todos_produtos)
    
    return todos_produtos

if __name__ == "__main__":
    produtos = main()

