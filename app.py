import streamlit as st
import pandas as pd
import requests
import plotly.express as px

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
