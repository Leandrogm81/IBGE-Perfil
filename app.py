import streamlit as st
import pandas as pd
import requests
import plotly.express as px

def get_estados():
    """
    Busca a lista de estados brasileiros na API do IBGE.

    Returns:
        list: Lista de tuplas (nome_estado, id_estado) ou lista vazia em caso de erro.
    """
    try:
        response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome")
        response.raise_for_status()  # Lança exceção para erros HTTP
        estados_data = response.json()
        estados = [(estado['nome'], estado['id']) for estado in estados_data]
        return estados
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar estados: {e}")
        return []
    except ValueError as e: # Erro de parsing JSON
        print(f"Erro ao parsear JSON dos estados: {e}")
        return []

def buscar_dados_agrupados_por_estado(estado_id):
    """
    Busca dados de população masculina e feminina por município para um dado estado.

    Args:
        estado_id (int): ID do estado a ser consultado.

    Returns:
        pd.DataFrame: DataFrame com ['Município Nome', 'População Masculina', 'População Feminina']
                      ou DataFrame vazio em caso de erro.
    """
    municipios_url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado_id}/municipios"
    dados_coletados = []

    try:
        response_municipios = requests.get(municipios_url)
        response_municipios.raise_for_status()
        municipios_data = response_municipios.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar municípios para o estado {estado_id}: {e}")
        return pd.DataFrame(columns=['Município Nome', 'População Masculina', 'População Feminina'])
    except ValueError as e: # Erro de parsing JSON
        print(f"Erro ao parsear JSON dos municípios para o estado {estado_id}: {e}")
        return pd.DataFrame(columns=['Município Nome', 'População Masculina', 'População Feminina'])

    for municipio in municipios_data:
        id_municipio = municipio['id']
        nome_municipio = municipio['nome']
        pop_masculina = 0
        pop_feminina = 0

        # API para dados agregados por sexo
        # Variáveis: 214 (População Masculina), 215 (População Feminina)
        # Classificação: 2[6] (Sexo - Masculino, Feminino)
        # Período: 2022 (Último censo disponível com essa desagregação no momento da criação)
        dados_url = f"https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/2022/variaveis/214|215?localidades=N6[{id_municipio}]&classificacao=2[6]"

        try:
            response_dados = requests.get(dados_url)
            response_dados.raise_for_status()
            dados_populacao = response_dados.json()

            # Estrutura esperada:
            # dados_populacao é uma lista, uma para cada variável (214, 215)
            for item in dados_populacao:
                variavel_id = item['id']
                # Acessa os resultados. Pode não haver 'serie' se não houver dados.
                resultados = item.get('resultados', [])
                if resultados and resultados[0].get('series'):
                    serie_data = resultados[0]['series'][0].get('serie', {})
                    # O ano '2022' é a chave para o valor da população
                    pop_valor_str = serie_data.get('2022', '0')
                    try:
                        pop_valor_int = int(pop_valor_str)
                    except ValueError:
                        print(f"Valor de população não numérico para município {nome_municipio} ({id_municipio}), variável {variavel_id}: {pop_valor_str}")
                        pop_valor_int = 0 # Usa 0 se o valor não for um número

                    if variavel_id == '214': # População Masculina
                        pop_masculina = pop_valor_int
                    elif variavel_id == '215': # População Feminina
                        pop_feminina = pop_valor_int
                else:
                    # Se não houver 'series' ou 'resultados', significa que não há dados para essa variável/localidade
                    # print(f"Dados não encontrados para município {nome_municipio} ({id_municipio}), variável {variavel_id} na API.")
                    pass # Mantém 0 se não houver dados


        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar dados para o município {nome_municipio} ({id_municipio}): {e}")
            # Continua para o próximo município, mas registra o erro.
            # Os valores de pop_masculina e pop_feminina permanecerão 0 para este município.
        except ValueError as e: # Erro de parsing JSON
            print(f"Erro ao parsear JSON para o município {nome_municipio} ({id_municipio}): {e}")
            # Mesma lógica de erro acima.
        except IndexError as e:
            print(f"Erro de índice ao processar dados para {nome_municipio} ({id_municipio}), possivelmente estrutura de JSON inesperada: {e}")
            # Mesma lógica de erro acima.


        dados_coletados.append({
            'Município Nome': nome_municipio,
            'População Masculina': pop_masculina,
            'População Feminina': pop_feminina
        })

    if not dados_coletados: # Se nenhum dado foi coletado (ex: estado sem municípios ou todos falharam)
        return pd.DataFrame(columns=['Município Nome', 'População Masculina', 'População Feminina'])

    return pd.DataFrame(dados_coletados)

# ... (todo o resto do seu código, incluindo a configuração da página e as funções, permanece igual) ...

# --- Interface do Usuário ---

# Inicializa o estado de busca na sessão, se não existir
if 'searching' not in st.session_state:
    st.session_state.searching = False

estados_lista = get_estados()
if estados_lista:
    estado_nome, estado_id = st.selectbox(
        "Selecione o Estado",
        options=estados_lista,
        format_func=lambda x: x[0]
    )

    min_pop = st.slider(
        "População total mínima do município",
        min_value=0, max_value=200000, value=0, step=5000
    )

    # O botão agora define o estado 'searching' como True quando clicado
    # e fica desabilitado enquanto 'searching' for True.
    if st.button(f"Buscar dados para {estado_nome}", disabled=st.session_state.searching):
        st.session_state.searching = True
        # Usamos um 'try...finally' para garantir que o estado seja resetado
        # mesmo que ocorra um erro durante a busca.
        try:
            with st.spinner(f"Carregando e processando dados de {estado_nome}... Isso levará alguns segundos."):
                # ... (toda a lógica de busca e exibição de dados que já existe) ...
                df_full = buscar_dados_agrupados_por_estado(estado_id)

                if df_full.empty:
                    st.warning("Não foi possível carregar os dados para este estado.")
                else:
                    # ... (resto da sua lógica de processamento e exibição dos gráficos)
                    df = df_full[df_full['População Feminina'] > df_full['População Masculina']].copy()
                    df['População Total'] = df['População Masculina'] + df['População Feminina']
                    df = df[df['População Total'] >= min_pop]

                    if df.empty:
                         st.warning("Nenhum município encontrado com os filtros aplicados.")
                    else:
                        # ... (código para exibir dataframe, gráficos, etc.)
                        st.subheader(f"Municípios com mais mulheres que homens em {estado_nome}")
                        st.dataframe(df, use_container_width=True) # Exemplo
                        # E assim por diante...
        finally:
            # Ao final de tudo (sucesso ou falha), reseta o estado para reabilitar o botão.
            st.session_state.searching = False
            # Força um re-run para que o botão apareça habilitado imediatamente
            st.rerun() 
