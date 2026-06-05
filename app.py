import pandas as pd
import streamlit as st
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Controle Financeiro Pessoal",
    page_icon="💰",
    layout="wide"
)

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
SHEET_NAME = st.secrets["SHEET_NAME"]

def carregar_dados():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPE
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    dados = sheet.get_all_records()

    return pd.DataFrame(dados)


def converter_moeda(valor):
    if pd.isna(valor) or valor == "":
        return 0.0

    valor = str(valor)
    valor = valor.replace("R$", "")
    valor = valor.replace(".", "")
    valor = valor.replace(",", ".")
    valor = valor.strip()

    try:
        return float(valor)
    except ValueError:
        return 0.0


def formatar_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preparar_dados(df):
    df = df.copy()

    df["DATA"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["DATA"])

    df["VALOR ENTRADA NUM"] = df["VALOR ENTRADA"].apply(converter_moeda)
    df["VALOR SAÍDA NUM"] = df["VALOR SAÍDA"].apply(converter_moeda)
    df["VALOR NUM"] = df["VALOR"].apply(converter_moeda)

    df["MÊS_REF"] = df["DATA"].dt.strftime("%m/%Y")
    df["ANO_MES"] = df["DATA"].dt.strftime("%Y-%m")

    return df



try:
    df_original = carregar_dados()
except Exception as e:
    st.error("Erro ao carregar dados da planilha.")
    st.exception(e)
    st.stop()

df = preparar_dados(df_original)

st.title("💰 Controle Financeiro Pessoal")

meses_disponiveis = (
    df[["MÊS_REF", "ANO_MES"]]
    .drop_duplicates()
    .sort_values("ANO_MES", ascending=False)
)

opcoes_meses = meses_disponiveis["MÊS_REF"].tolist()

mes_atual = pd.Timestamp.today().strftime("%m/%Y")

indice_mes_atual = (
    opcoes_meses.index(mes_atual)
    if mes_atual in opcoes_meses
    else 0
)

mes_selecionado = st.selectbox(
    "📅 Competência",
    opcoes_meses,
    index=indice_mes_atual
)

# Saldo atual geral apenas do centro de custo Necessidades Básicas
df_necessidades_basicas = df[
    df["CENTRO DE CUSTO"].astype(str).str.strip().str.lower() == "necessidades básicas"
]

saldo_atual = (
    df_necessidades_basicas["VALOR ENTRADA NUM"].sum()
    - df_necessidades_basicas["VALOR SAÍDA NUM"].sum()
)

cor_saldo_atual = "#16a34a" if saldo_atual >= 0 else "#dc2626"

st.sidebar.header("Filtros")

tipo_periodo = st.sidebar.radio(
    "Período",
    ["Mês", "Todas as datas", "Período personalizado"],
    index=0
)

if tipo_periodo == "Todas as datas":
    df_filtrado = df.copy()

elif tipo_periodo == "Mês":
    df_filtrado = df[df["MÊS_REF"] == mes_selecionado]


else:
    data_min = df["DATA"].min().date()
    data_max = df["DATA"].max().date()

    data_inicio = st.sidebar.date_input(
        "Data inicial",
        data_min,
        format="DD/MM/YYYY"
    )

    data_fim = st.sidebar.date_input(
        "Data final",
        data_max,
        format="DD/MM/YYYY"
    )

    df_filtrado = df[
        (df["DATA"].dt.date >= data_inicio) &
        (df["DATA"].dt.date <= data_fim)
    ]

centros = sorted(df_filtrado["CENTRO DE CUSTO"].dropna().unique().tolist())

centro_padrao = [
    centro for centro in centros
    if str(centro).strip().lower() == "necessidades básicas"
]

st.sidebar.markdown("### Centro de custo")

centros_selecionados = []

for centro in centros:
    marcado = centro in centro_padrao

    if st.sidebar.checkbox(centro, value=marcado, key=f"centro_{centro}"):
        centros_selecionados.append(centro)

df_filtrado = df_filtrado[
    df_filtrado["CENTRO DE CUSTO"].isin(centros_selecionados)
]

total_entrada = df_filtrado["VALOR ENTRADA NUM"].sum()
total_saida = df_filtrado["VALOR SAÍDA NUM"].sum()
saldo = total_entrada - total_saida

st.markdown("### Resumo financeiro")

cor_saldo = "#16a34a" if saldo >= 0 else "#dc2626"

st.markdown(
    f"""
    <style>
    .card-resumo {{
        background: #ffffff;
        padding: 22px;
        border-radius: 18px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.08);
        border: 1px solid #eeeeee;
        margin-bottom: 12px;
    }}

    .card-titulo {{
        font-size: 14px;
        color: #666666;
        margin-bottom: 8px;
        font-weight: 600;
    }}

    .card-valor {{
        font-size: 30px;
        font-weight: 800;
        line-height: 1.1;
    }}

    .entrada {{
        color: #16a34a;
    }}

    .saida {{
        color: #dc2626;
    }}

    .saldo {{
        color: {cor_saldo};
    }}

    @media (max-width: 768px) {{
        .card-resumo {{
            padding: 18px;
            border-radius: 16px;
        }}

        .card-valor {{
            font-size: 26px;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True
)

col0, col1, col2, col3 = st.columns(4)

with col0:
    st.markdown(
        f"""
        <div class="card-resumo">
            <div class="card-titulo">Saldo atual - Necessidades Básicas</div>
            <div class="card-valor" style="color:{cor_saldo_atual};">{formatar_real(saldo_atual)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col1:
    st.markdown(
        f"""
        <div class="card-resumo">
            <div class="card-titulo">Entradas do filtro</div>
            <div class="card-valor entrada">{formatar_real(total_entrada)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div class="card-resumo">
            <div class="card-titulo">Saídas do filtro</div>
            <div class="card-valor saida">{formatar_real(total_saida)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div class="card-resumo">
            <div class="card-titulo">Saldo do filtro</div>
            <div class="card-valor saldo">{formatar_real(saldo)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.divider()

st.subheader("Gastos por Categoria")

gastos_categoria = (
    df_filtrado[df_filtrado["VALOR SAÍDA NUM"] > 0]
    .groupby("CATEGORIA UNIFICADA", as_index=False)["VALOR SAÍDA NUM"]
    .sum()
    .sort_values("VALOR SAÍDA NUM", ascending=False)
)

if gastos_categoria.empty:
    st.info("Nenhum gasto encontrado para os filtros selecionados.")
else:
    fig_categoria = px.bar(
        gastos_categoria,
        x="VALOR SAÍDA NUM",
        y="CATEGORIA UNIFICADA",
        orientation="h",
        title="Gastos por Categoria",
        text_auto=True
    )

    fig_categoria.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_title="Valor",
        yaxis_title="Categoria"
    )

    st.plotly_chart(fig_categoria, use_container_width=True)

st.divider()

st.subheader("Lançamentos")

colunas_tabela = [
    "DATA",
    "FORNECEDOR",
    "DESCRIÇÃO",
    "CENTRO DE CUSTO",
    "VALOR ENTRADA",
    "VALOR SAÍDA",
    "CATEGORIA UNIFICADA",
    "TIPO DE LANÇAMENTO",
    "ANEXO"
]

df_tabela = df_filtrado[colunas_tabela].copy()
df_tabela["DATA"] = df_tabela["DATA"].dt.strftime("%d/%m/%Y")

st.dataframe(
    df_tabela,
    use_container_width=True,
    hide_index=True
)
