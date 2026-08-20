"""Pruebas de la logica pura de parseo de CopilotTeamsActions -- no
requieren tener Copilot/Teams abiertos, solo cubren las funciones que
convierten celdas crudas de UI Automation en filas limpias."""
from __future__ import annotations

from engine.actions.copilot_teams import (
    CopilotTeamsActions,
    crear_diccionario_de_acciones,
    formatear_mensaje_teams,
)


def test_quitar_citation_recorta_el_texto_del_boton_de_cita() -> None:
    entrada = "El flujo no completó su ejecución. Citation: PROD - Error en 901_FIN_CXP_2_AltaAclaracion"
    assert CopilotTeamsActions._quitar_citation(entrada) == "El flujo no completó su ejecución."


def test_quitar_citation_no_toca_texto_sin_cita() -> None:
    entrada = "No pudo crear hoja Sheet2 porque ya existe."
    assert CopilotTeamsActions._quitar_citation(entrada) == entrada


def test_quitar_citation_celda_que_es_solo_la_cita_usa_texto_de_respaldo() -> None:
    """Regresion del bug real: una columna 'Evidencia' que es solo el
    icono de cita (sin texto propio) no debe quedar como 'Citation: ...'."""
    entrada = "Citation: PROD - Error en 113_FIN_NOM_ConsolidacionIncapacidadesIMSS"
    assert CopilotTeamsActions._quitar_citation(entrada) == "(sin detalle adicional)"


def test_contar_columnas_encabezado_detecta_el_ancho_correcto() -> None:
    celdas = ["", "Hora", "Proceso", "Error", "Impacto", "", "10:39", "algo", "algo2", "algo3"]
    assert CopilotTeamsActions._contar_columnas_encabezado(celdas) == 4


def test_contar_columnas_encabezado_vacio_devuelve_cero() -> None:
    assert CopilotTeamsActions._contar_columnas_encabezado([]) == 0
    assert CopilotTeamsActions._contar_columnas_encabezado(["", ""]) == 0


def test_formatear_mensaje_teams_usa_etiquetas_reales_del_encabezado() -> None:
    """Regresion del bug real: el mensaje enviado decia 'Impacto:' aunque
    la tabla real traia una columna 'Evidencia' -- debe usar la etiqueta
    que de verdad trajo la tabla, la que sea."""
    encabezado = ["Hora", "Proceso", "Error detectado", "Evidencia"]
    filas = [["10:39", "901_FIN_CXP_2_AltaAclaracion", "An action failed.", "(sin detalle adicional)"]]

    mensaje = formatear_mensaje_teams(encabezado, filas)

    assert "Impacto" not in mensaje  # nunca debe inventar una etiqueta que no vino en la tabla
    assert "Evidencia" not in mensaje  # la celda vacia/solo-cita se omite, no se manda con texto vacio
    assert "10:39" in mensaje
    assert "901_FIN_CXP_2_AltaAclaracion" in mensaje
    assert "Error detectado: An action failed." in mensaje


def test_formatear_mensaje_teams_usa_columna_impacto_cuando_si_viene() -> None:
    encabezado = ["Hora", "Proceso", "Error detectado", "Impacto observado"]
    filas = [["09:47", "112_COM_FRE", "Error al leer Excel", "Falla en lectura de rango"]]

    mensaje = formatear_mensaje_teams(encabezado, filas)

    assert "Impacto observado: Falla en lectura de rango" in mensaje


def test_palabras_significativas_ignora_sintaxis_markdown_y_tokens_cortos() -> None:
    """Regresion del bug real: al pegar una tabla markdown copiada de
    Copilot en Teams, Teams reescribe los links/tabla y el texto nunca
    sera char-por-char igual -- por eso la verificacion se hace por
    cobertura de palabras significativas, no por igualdad exacta."""
    origen_markdown = (
        "| Proceso | Hora | [PROD - Error en 901_FIN_CXP_2_AltaAclaracion](https://outlook.office365.com/owa/x) |"
    )
    pegado_en_teams = "Proceso Hora PROD - Error en 901_FIN_CXP_2_AltaAclaracion"

    esperadas = CopilotTeamsActions._palabras_significativas(origen_markdown)
    pegadas = CopilotTeamsActions._palabras_significativas(pegado_en_teams)
    cobertura = len(esperadas & pegadas) / max(len(esperadas), 1)

    assert cobertura >= 0.4
    assert "901_fin_cxp_2_altaaclaracion" in pegadas


def test_crear_diccionario_de_acciones_expone_las_acciones_esperadas() -> None:
    acciones = CopilotTeamsActions(logger=None)
    diccionario = crear_diccionario_de_acciones(acciones)

    esperadas = {
        "abrir_copilot",
        "buscar_agente",
        "clickear_agente",
        "enviar_prompt",
        "leer_tabla_de_respuesta",
        "copiar_tabla_de_respuesta",
        "esperar_tabla_de_respuesta",
        "esperar_y_copiar_tabla",
        "copiar_respuesta_completa",
        "abrir_teams",
        "abrir_chat_propio",
        "pegar_y_enviar",
    }
    assert esperadas <= diccionario.keys()
    assert all(callable(f) for f in diccionario.values())
