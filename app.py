import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# --- Configuração da Página e Cabeçalho ---
st.set_page_config(page_title="Perfil Populacional - IBGE", layout="wide")

st.title("Perfil Populacional dos Municípios (Censo 2010)")
st.markdown(
    """
    Este aplicativo analisa os dados do Censo de 2010 do IBGE para encontrar municípios com mais mulheres do que homens.
    Ele também exibe informações sobre a proporção de mulheres jovens (15 a 29 anos), a renda per capita e o percentual de domicílios chefiados por mulheres.
    """
)
st.info(
    "A consulta foi otimizada para ser mais rápida. Agora, todos os dados de um estado são carregados de uma só vez."
)

# --- Funções com Cache para Performance ---

@st.cache_data
def get_estados():
    """Busca a lista de estados da API do IBGE e a armazena em cache."""
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
        response = requests.get(url)
        response.raise_for_status()  # Lança um erro para códigos de status ruins (4xx ou 5xx)
        estados = response.json()
        # Retorna uma lista ordenada de tuplas (nome, id)
        return sorted([(uf['nome'], uf['id']) for uf in estados])
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar a lista de estados: {e}")
        return []

@st.cache_data
def buscar_dados_agrupados_por_estado(estado_id):
    """
    Busca todos os dados necessários para um estado em chamadas de API agrupadas,
    em vez de uma por município. Isso é muito mais rápido.
    """
    # URLs para buscar dados de TODOS os municípios do estado de uma vez
    # Variáveis: t=tabela, p=período, v=variável, c1=sexo, c2=grupo de idade, c315=responsável pelo domicílio
    # Localidade: N3[{estado_id}] busca no estado, /N6 busca todos os municípios dentro desse estado.
    urls = {
        "populacao": f"https://apisidra.ibge.gov.br/values/t/200/p/2010/v/93/c1/1,2/c2/all/n6/all/d/N3%20{estado_id}",
        "renda": f"https://apisidra.ibge.gov.br/values/t/5938/p/2010/v/38/n6/all/d/N3%20{estado_id}",
        "chefia": f"https://apisidra.ibge.gov.br/values/t/1356/p/2010/v/207/c315/2/n6/all/d/N3%20{estado_id}",
    }

    data_map = {}

    try:
        # 1. Processar dados de População por Sexo e Idade
        pop_res = requests.get(urls["populacao"], timeout=30).json()
        # O cabeçalho (primeiro item) contém os nomes das colunas
        header = pop_res[0]
        for row in pop_res[1:]:
            item = dict(zip(header.values(), row.values()))
            cod_mun = item['Município (Código)']
            
            if cod_mun not in data_map:
                data_map[cod_mun] = {
                    "Município": item['Município'].split(' - ')[0],
                    "População Feminina": 0, "População Masculina": 0,
                    "Mulheres Jovens (15-29)": 0
                }
            
            valor = int(item['V'])
            if item['Sexo'] == 'Masculino' and item['Grupo de idade'] == 'Total':
                data_map[cod_mun]['População Masculina'] += valor
            elif item['Sexo'] == 'Feminino':
                if item['Grupo de idade'] == 'Total':
                    data_map[cod_mun]['População Feminina'] += valor
                # Agregando faixas de idade para "15 a 29 anos"
                elif item['Grupo de idade'] in ["15 a 19 anos", "20 a 24 anos", "25 a 29 anos"]:
                    data_map[cod_mun]['Mulheres Jovens (15-29)'] += valor
        
        # 2. Processar dados de Renda Per Capita
        renda_res = requests.get(urls["renda"], timeout=30).json()
        header = renda_res[0]
        for row in renda_res[1:]:
            item = dict(zip(header.values(), row.values()))
            cod_mun = item['Município (Código)']
            if cod_mun in data_map:
                data_map[cod_mun]['Renda Per Capita (R$)'] = float(item['V'])

        # 3. Processar dados de Chefia Feminina
        chefia_res = requests.get(urls["chefia"], timeout=30).json()
        header = chefia_res[0]
        for row in chefia_res[1:]:
            item = dict(zip(header.values(), row.values()))
            cod_mun = item['Município (Código)']
            if cod_mun in data_map:
                 data_map[cod_mun]['Domicílios com Chefia Feminina'] = int(item['V'])

    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        st.error(f"Falha ao buscar ou processar os dados do IBGE: {e}")
        return pd.DataFrame() # Retorna DF vazio em caso de erro

    # Converter o dicionário de mapas em uma lista de dicionários
    dados_finais = [v for k, v in data_map.items()]
    return pd.DataFrame(dados_finais)


# --- Interface do Usuário ---

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

    if st.button(f"Buscar dados para {estado_nome}"):
        with st.spinner(f"Carregando e processando dados de {estado_nome}... Isso levará alguns segundos."):
            # Busca os dados (rápido devido ao cache e à chamada agrupada)
            df_full = buscar_dados_agrupados_por_estado(estado_id)

            if df_full.empty:
                st.warning("Não foi possível carregar os dados para este estado.")
            else:
                # Filtrar municípios com mais mulheres que homens
                df = df_full[df_full['População Feminina'] > df_full['População Masculina']].copy()

                # Calcular totais e percentuais
                df['População Total'] = df['População Masculina'] + df['População Feminina']
                df['% Mulheres Jovens (15-29)'] = (df['Mulheres Jovens (15-29)'] / df['População Feminina'] * 100).round(2)
                df['% Chefia Feminina Domicílio'] = (df['Domicílios com Chefia Feminina'] / df['População Total'] * 100).round(2)

                # Aplicar filtro de população mínima
                df = df[df['População Total'] >= min_pop]

                if df.empty:
                    st.warning("Nenhum município encontrado com os filtros aplicados (mais mulheres que homens e população mínima).")
                else:
                    st.subheader(f"Municípios com mais mulheres que homens em {estado_nome}")
                    st.dataframe(df[[
                        'Município', 'População Feminina', 'População Masculina', 'População Total',
                        '% Mulheres Jovens (15-29)', 'Renda Per Capita (R$)', '% Chefia Feminina Domicílio'
                    ]].sort_values('População Feminina', ascending=False), use_container_width=True)
                    
                    # --- Gráficos ---
                    st.markdown("---")
                    st.subheader("Análise Gráfica dos Top 10 Municípios")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("##### Top 10 por % de Mulheres Jovens (15-29 anos)")
                        top_jovem = df.nlargest(10, '% Mulheres Jovens (15-29)')
                        fig1 = px.bar(top_jovem, x="Município", y="% Mulheres Jovens (15-29)", text_auto='.2f', title="")
                        st.plotly_chart(fig1, use_container_width=True)

                        st.markdown("##### Top 10 por % Chefia Feminina de Domicílio")
                        top_chefia = df.nlargest(10, '% Chefia Feminina Domicílio')
                        fig3 = px.bar(top_chefia, x="Município", y="% Chefia Feminina Domicílio", text_auto='.2f', title="")
                        st.plotly_chart(fig3, use_container_width=True)
                    
                    with col2:
                        st.markdown("##### Top 10 por Renda Per Capita")
                        df_renda = df.dropna(subset=['Renda Per Capita (R$)'])
                        top_renda = df_renda.nlargest(10, 'Renda Per Capita (R$)')
                        fig2 = px.bar(top_renda, x="Município", y="Renda Per Capita (R$)", text_auto='.2f', title="")
                        st.plotly_chart(fig2, use_container_width=True)
                    
                    # --- Download ---
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Baixar Tabela Completa (CSV)",
                        data=csv,
                        file_name=f"dados_mulheres_{estado_nome.lower().replace(' ', '_')}.csv",
                        mime="text/csv",
            )
                    
