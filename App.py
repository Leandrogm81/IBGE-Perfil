import streamlit as st
import pandas as pd
import requests
import time
import plotly.express as px

st.set_page_config(page_title="Perfil Populacional - IBGE", layout="wide")

st.title("Municípios com Mais Mulheres do que Homens (Censo 2010)")
st.markdown(
    """
    Este aplicativo mostra, por município, onde há mais mulheres que homens.  
    Exibe também dados sobre renda per capita, mulheres jovens (15 a 29 anos) e domicílios chefiados por mulheres (Censo 2010 IBGE).
    """
)

# Seleção de estado
estados_url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
estados = requests.get(estados_url).json()
estados_lista = sorted([(uf['nome'], uf['id']) for uf in estados])
estado_nome = st.selectbox("Selecione o Estado", [e[0] for e in estados_lista])
estado_id = [e[1] for e in estados_lista if e[0] == estado_nome][0]

# Parâmetros extras para filtro
min_pop = st.slider("População mínima do município", min_value=0, max_value=50000, value=0, step=1000)

# Buscar municípios do estado selecionado
mun_url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado_id}/municipios"
mun_res = requests.get(mun_url).json()
mun_lista = [(m['nome'], m['id']) for m in mun_res]

st.info("Aguarde! Pode demorar 2 a 5 minutos para consultar todos os municípios do estado...")

dados_lista = []
bar = st.progress(0)
total = len(mun_lista)

for i, (nome, cod) in enumerate(mun_lista):
    try:
        # População por sexo e faixa etária
        url_pop = f"https://sidra.ibge.gov.br/geratabela?format=json&tabela=200&localidade=6|{cod}&periodo=2010"
        pop = requests.get(url_pop, timeout=8).json()
        masc = fem = jovens_fem = 0
        for l in pop:
            if "Masculino" in l['Sexo'] and "Total" in l['Grupo de idade']:
                masc += int(l['Valor'].replace('.', ''))
            if "Feminino" in l['Sexo'] and "Total" in l['Grupo de idade']:
                fem += int(l['Valor'].replace('.', ''))
            if "Feminino" in l['Sexo'] and "15 a 29" in l['Grupo de idade']:
                jovens_fem += int(l['Valor'].replace('.', ''))

        total_pop = masc + fem
        if total_pop < min_pop:
            bar.progress((i+1)/total)
            continue

        # Renda per capita
        url_renda = f"https://sidra.ibge.gov.br/geratabela?format=json&tabela=5938&localidade=6|{cod}&periodo=2010"
        renda = requests.get(url_renda, timeout=8).json()
        renda_pc = renda[0]['Valor'].replace(',', '.') if renda else None

        # Chefia feminina de domicílio
        url_chefia = f"https://sidra.ibge.gov.br/geratabela?format=json&tabela=1356&localidade=6|{cod}&periodo=2010"
        chefia = requests.get(url_chefia, timeout=8).json()
        chefia_fem = 0
        for l in chefia:
            if "Feminino" in l['Sexo do responsável']:
                chefia_fem += int(l['Valor'].replace('.', ''))

        if fem > masc:  # Só lista cidades com mais mulheres
            perc_jovem_fem = (jovens_fem / fem * 100) if fem else 0
            perc_chefia_fem = (chefia_fem / total_pop * 100) if total_pop else 0
            dados_lista.append({
                "Município": nome,
                "População Feminina": fem,
                "População Masculina": masc,
                "% Mulheres Jovens (15-29)": round(perc_jovem_fem, 2),
                "Renda Per Capita (R$)": renda_pc,
                "% Chefia Feminina": round(perc_chefia_fem, 2),
                "Total População": total_pop,
            })
    except Exception:
        pass
    bar.progress((i+1)/total)

bar.empty()

if not dados_lista:
    st.warning("Nenhum município com mais mulheres que homens encontrado nesse estado com esse filtro.")
else:
    df = pd.DataFrame(dados_lista)
    # Ordenação padrão: mais mulheres
    df = df.sort_values(by=["População Feminina"], ascending=False)

    st.subheader(f"Municípios com mais mulheres que homens em {estado_nome}")
    st.dataframe(df, use_container_width=True)

    st.markdown("#### Top 10 municípios por % de mulheres jovens (15-29 anos)")
    top_jovem = df.sort_values(by=["% Mulheres Jovens (15-29)"], ascending=False).head(10)
    fig1 = px.bar(top_jovem, x="Município", y="% Mulheres Jovens (15-29)", text="% Mulheres Jovens (15-29)")
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("#### Top 10 municípios por renda per capita")
    try:
        df_renda = df.dropna(subset=["Renda Per Capita (R$)"])
        df_renda["Renda Per Capita (R$)"] = df_renda["Renda Per Capita (R$)"].astype(float)
        top_renda = df_renda.sort_values(by=["Renda Per Capita (R$)"], ascending=False).head(10)
        fig2 = px.bar(top_renda, x="Município", y="Renda Per Capita (R$)", text="Renda Per Capita (R$)")
        st.plotly_chart(fig2, use_container_width=True)
    except Exception:
        st.info("Não foi possível gerar gráfico de renda.")

    st.markdown("#### Top 10 municípios por % chefia feminina")
    top_chefia = df.sort_values(by=["% Chefia Feminina"], ascending=False).head(10)
    fig3 = px.bar(top_chefia, x="Município", y="% Chefia Feminina", text="% Chefia Feminina")
    st.plotly_chart(fig3, use_container_width=True)

    # Download CSV
    csv = df.to_csv(index=False).encode()
    st.download_button("Baixar tabela completa (CSV)", data=csv, file_name=f"mulheres_mais_{estado_nome}.csv")
