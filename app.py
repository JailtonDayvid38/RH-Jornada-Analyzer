import streamlit as st
import pandas as pd
from io import BytesIO

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="RH Jornada Analyzer",
    page_icon="🕒",
    layout="wide"
)

st.title("🕒 RH Jornada Analyzer")

st.write(
    """
    Sistema para análise de jornada de trabalho,
    interjornada e possíveis inconsistências.
    """
)

st.divider()


# =========================================================
# IMPORTAÇÃO DO ARQUIVO
# =========================================================

st.subheader("1. Importar arquivo de ponto")

arquivo = st.file_uploader(
    "Selecione uma planilha Excel ou arquivo CSV",
    type=["xlsx", "csv"]
)


# Todo o processamento abaixo só acontece
# quando o usuário carregar um arquivo.
if arquivo is not None:

    # =====================================================
    # LEITURA DO ARQUIVO
    # =====================================================

    try:

        if arquivo.name.lower().endswith(".xlsx"):
            dados = pd.read_excel(arquivo)

        elif arquivo.name.lower().endswith(".csv"):
            dados = pd.read_csv(arquivo)

        st.success("Arquivo carregado com sucesso!")

    except Exception as erro:

        st.error(
            f"Não foi possível ler o arquivo. Erro: {erro}"
        )

        st.stop()


    # =====================================================
    # VALIDAÇÃO DAS COLUNAS
    # =====================================================

    colunas_obrigatorias = [
        "Matrícula",
        "Nome",
        "Data",
        "Entrada",
        "Saída"
    ]

    colunas_faltantes = [
        coluna
        for coluna in colunas_obrigatorias
        if coluna not in dados.columns
    ]

    if colunas_faltantes:

        st.error(
            "A planilha não possui todas as colunas obrigatórias."
        )

        st.write(
            "Colunas que estão faltando:"
        )

        st.write(colunas_faltantes)

        st.stop()


    # =====================================================
    # CONVERSÃO DE DATA E HORÁRIO
    # =====================================================

    dados["Data"] = pd.to_datetime(
        dados["Data"],
        errors="coerce"
    )

    dados["DataHoraEntrada"] = pd.to_datetime(
        dados["Data"].dt.strftime("%Y-%m-%d")
        + " "
        + dados["Entrada"].astype(str),
        errors="coerce"
    )

    dados["DataHoraSaida"] = pd.to_datetime(
        dados["Data"].dt.strftime("%Y-%m-%d")
        + " "
        + dados["Saída"].astype(str),
        errors="coerce"
    )


    # =====================================================
    # JORNADAS QUE TERMINAM APÓS A MEIA-NOITE
    # =====================================================

    # Exemplo de jornada que ultrapassa a meia-noite:
    # Entrada: 22:00
    # Saída:   06:00
    # Nesse caso, a saída pertence ao dia seguinte.

    jornada_noturna = (
        dados["DataHoraSaida"]
        < dados["DataHoraEntrada"]
    )

    dados.loc[
        jornada_noturna,
        "DataHoraSaida"
    ] = (
        dados.loc[
            jornada_noturna,
            "DataHoraSaida"
        ]
        + pd.Timedelta(days=1)
    )


    # =====================================================
    # ORGANIZAÇÃO DOS REGISTROS
    # =====================================================

    # Para calcular corretamente a interjornada,
    # precisamos organizar cada colaborador
    # cronologicamente.

    dados = dados.sort_values(
        by=[
            "Matrícula",
            "DataHoraEntrada"
        ]
    )


    # =====================================================
    # IDENTIFICAÇÃO DA SAÍDA ANTERIOR
    # =====================================================

    # Para cada colaborador, buscamos a saída da jornada
    # imediatamente anterior.
    # shift(1) traz o valor da linha anterior.
    
    dados["SaidaAnterior"] = (
        dados
        .groupby("Matrícula")["DataHoraSaida"]
        .shift(1)
    )


    # =====================================================
    # CÁLCULO DA INTERJORNADA
    # =====================================================

    dados["InterjornadaHoras"] = (
        (
            dados["DataHoraEntrada"]
            - dados["SaidaAnterior"]
        )
        .dt.total_seconds()
        / 3600
    )


    # =====================================================
    # REGRA DE INTERJORNADA
    # =====================================================

    LIMITE_INTERJORNADA = 11


    # -----------------------------------------------------
    # CÁLCULO DO DÉFICIT
    # -----------------------------------------------------

    dados["DeficitHoras"] = (
        LIMITE_INTERJORNADA
        - dados["InterjornadaHoras"]
    ).clip(lower=0)


    # -----------------------------------------------------
    # CLASSIFICAÇÃO DA INTERJORNADA
    # -----------------------------------------------------

    def classificar_interjornada(horas):
        """
        Classifica o descanso entre duas jornadas.

        Primeira jornada:
        não existe jornada anterior para comparação.

        Regular:
        descanso igual ou superior ao limite definido.

        Ocorrência:
        descanso inferior ao limite.
        """

        if pd.isna(horas):
            return "Primeira jornada"

        if horas < LIMITE_INTERJORNADA:
            return "⚠️ Interjornada inferior a 11h"

        return "✅ Regular"


    dados["Status"] = (
        dados["InterjornadaHoras"]
        .apply(classificar_interjornada)
    )


    # =====================================================
    # INDICADORES GERAIS
    # =====================================================

    total_colaboradores = (
        dados["Matrícula"]
        .nunique()
    )

    total_registros = len(dados)

    total_ocorrencias = (
        dados["Status"]
        == "⚠️ Interjornada inferior a 11h"
    ).sum()

    total_deficit = (
        dados["DeficitHoras"]
        .sum()
    )


    # =====================================================
    # DASHBOARD
    # =====================================================

    st.subheader("📊 Resumo da análise")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            label="Colaboradores",
            value=total_colaboradores
        )

    with col2:

        st.metric(
            label="Registros analisados",
            value=total_registros
        )

    with col3:

        st.metric(
            label="Ocorrências",
            value=total_ocorrencias
        )

    with col4:

        st.metric(
            label="Déficit total",
            value=f"{total_deficit:.2f} h"
        )

    st.divider()


    # =====================================================
    # RESULTADO COMPLETO
    # =====================================================

    st.subheader("2. Resultado da análise")

    resultado = dados[
        [
            "Matrícula",
            "Nome",
            "DataHoraEntrada",
            "DataHoraSaida",
            "SaidaAnterior",
            "InterjornadaHoras",
            "DeficitHoras",
            "Status"
        ]
    ].copy()


    # Arredondamos para duas casas decimais.

    resultado["InterjornadaHoras"] = (
        resultado["InterjornadaHoras"]
        .round(2)
    )

    resultado["DeficitHoras"] = (
        resultado["DeficitHoras"]
        .round(2)
    )


    st.dataframe(
        resultado,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # OCORRÊNCIAS IDENTIFICADAS
    # =====================================================

    ocorrencias = resultado[
        resultado["Status"]
        == "⚠️ Interjornada inferior a 11h"
    ].copy()


    st.subheader("3. Ocorrências identificadas")


    if ocorrencias.empty:

        st.success(
            "Nenhuma ocorrência de interjornada "
            "inferior a 11 horas foi encontrada."
        )

    else:

        st.warning(
            f"Foram encontradas "
            f"{len(ocorrencias)} ocorrência(s)."
        )

        st.dataframe(
            ocorrencias,
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # EXPORTAÇÃO PARA EXCEL
    # =====================================================

    st.subheader("4. Exportar relatório")


    def gerar_excel(
        resultado_completo,
        ocorrencias_encontradas
    ):
        """
        Gera um arquivo Excel em memória.

        O arquivo terá duas abas:

        1. Resultado Completo
        2. Ocorrências

        BytesIO permite criar o arquivo
        sem precisar salvá-lo fisicamente
        antes do download.
        """

        buffer = BytesIO()

        with pd.ExcelWriter(
            buffer,
            engine="openpyxl"
        ) as writer:

            resultado_completo.to_excel(
                writer,
                sheet_name="Resultado Completo",
                index=False
            )

            ocorrencias_encontradas.to_excel(
                writer,
                sheet_name="Ocorrências",
                index=False
            )

        buffer.seek(0)

        return buffer


    arquivo_excel = gerar_excel(
        resultado,
        ocorrencias
    )


    st.download_button(
        label="📥 Baixar relatório em Excel",
        data=arquivo_excel,
        file_name="relatorio_interjornada.xlsx",
        mime=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


    # =====================================================
    # INFORMAÇÃO FINAL
    # =====================================================

    st.info(
        """
        O sistema identifica intervalos inferiores ao
        parâmetro configurado de 11 horas entre jornadas.

        O déficit apresentado representa a diferença
        necessária para atingir esse parâmetro e não deve
        ser interpretado automaticamente como quantidade
        de horas a pagar.
        """
    )