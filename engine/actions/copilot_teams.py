"""Acciones reutilizables para automatizar Microsoft 365 Copilot y
Microsoft Teams via UI Automation (pywinauto) -- sin API, sin extension
de navegador, tal como se necesita en este equipo.

Cada metodo es una accion con nombre claro. ACCIONES (al final, via
crear_diccionario_de_acciones) las expone como diccionario nombre->funcion
para poder referenciar/componer pasos por nombre en vez de llamar
metodos sueltos -- pensado para reusarse desde cualquier automation.py.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import win32api
import win32clipboard
import win32con
import win32process
from pywinauto import Application, findwindows

TITULO_COPILOT = "Microsoft 365 Copilot"
EJECUTABLE_TEAMS = "ms-teams.exe"


def _proceso_de_ventana_es(pid: int, nombre_exe: str) -> bool:
    """Confirma el ejecutable real detras de un PID -- mas preciso que
    filtrar solo por titulo, que puede coincidir por accidente con otra
    ventana (nos paso con Teams y una terminal con titulo parecido)."""
    try:
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        ruta = win32process.GetModuleFileNameEx(handle, 0)
        return nombre_exe.lower() in ruta.lower()
    except Exception:
        return False


@dataclass
class ResultadoCopilot:
    """tipo: 'tabla' | 'texto' | 'error' -- para que quien use el
    resultado sepa si puede tratarlo como datos estructurados (filas en
    `detalle['filas']`) o solo como texto plano."""

    tipo: str
    contenido: str
    detalle: dict[str, Any] = field(default_factory=dict)


class CopilotTeamsActions:
    def __init__(self, logger) -> None:
        self.logger = logger
        self._ventana_copilot = None
        self._ventana_teams = None

    # ---------- Microsoft 365 Copilot ----------

    def abrir_copilot(self):
        app = Application(backend="uia").connect(title=TITULO_COPILOT)
        self._ventana_copilot = app.window(title=TITULO_COPILOT)
        self._ventana_copilot.set_focus()
        self.logger.info("Conectado a %s", TITULO_COPILOT)
        return self._ventana_copilot

    def buscar_agente(self, nombre: str):
        enlaces = self._ventana_copilot.descendants(control_type="Hyperlink")
        return next(e for e in enlaces if e.window_text().strip() == nombre)

    def clickear_agente(self, nombre: str) -> None:
        enlace = self.buscar_agente(nombre)
        enlace.click_input()
        time.sleep(2)
        self.logger.info("Agente abierto: %s", nombre)

    def enviar_prompt(self, nombre_agente: str, texto: str) -> None:
        caja = self._caja_mensaje_agente(nombre_agente)
        caja.click_input()
        caja.type_keys(texto, with_spaces=True, pause=0.03)
        caja.type_keys("{ENTER}")
        self.logger.info("Prompt enviado a %s: %s", nombre_agente, texto)

    def _caja_mensaje_agente(self, nombre_agente: str):
        ediciones = self._ventana_copilot.descendants(control_type="Edit")
        return next(e for e in ediciones if e.element_info.name == f"Message {nombre_agente}")

    def leer_tabla_de_respuesta(self) -> ResultadoCopilot:
        """Lee la tabla directamente del arbol de UI Automation (control
        'Table' con celdas 'DataItem'), en vez de copiar y parsear texto.

        Mas robusto que un boton de copiar: no depende de un icono que
        solo aparece al pasar el mouse por encima (hover), ni de
        coordenadas de pantalla, ni del portapapeles -- y de una vez
        entrega las columnas ya separadas.
        """
        tablas = self._ventana_copilot.descendants(control_type="Table")
        if not tablas:
            return ResultadoCopilot(tipo="error", contenido="", detalle={"motivo": "no hay tabla en la respuesta"})

        tabla = tablas[-1]  # la mas reciente
        celdas = [d.window_text().strip() for d in tabla.descendants(control_type="DataItem")]

        # Cada fila viene precedida por una celda vacia de relleno (columna
        # de indice sin encabezado visible); se agrupan de a NUM_COLUMNAS+1.
        num_columnas = self._contar_columnas_encabezado(celdas)
        if num_columnas == 0:
            return ResultadoCopilot(tipo="error", contenido="", detalle={"motivo": "no se detecto encabezado"})

        ancho_grupo = num_columnas + 1
        grupos = [celdas[i : i + ancho_grupo][1:] for i in range(0, len(celdas), ancho_grupo)]
        encabezado, *filas_crudas = grupos
        # _quitar_citation se aplica a TODAS las celdas, no solo a la ultima
        # columna -- que columna trae pegado el texto del boton de cita
        # varia segun como el agente arme la tabla (a veces es "Impacto",
        # otras veces es una columna "Evidencia" que es solo el icono).
        filas = [[self._quitar_citation(c) for c in fila] for fila in filas_crudas if any(fila)]

        contenido_plano = "\t".join(encabezado) + "\n" + "\n".join("\t".join(f) for f in filas)
        self.logger.info("Tabla leída de Copilot: %d columnas, %d filas", len(encabezado), len(filas))
        return ResultadoCopilot(
            tipo="tabla", contenido=contenido_plano, detalle={"encabezado": encabezado, "filas": filas}
        )

    @staticmethod
    def _contar_columnas_encabezado(celdas: list[str]) -> int:
        """La primera celda vacia marca el inicio del encabezado; cuenta
        cuantas celdas no vacias siguen antes de la proxima vacia."""
        for i, valor in enumerate(celdas):
            if valor == "":
                continue
            n = 0
            for v in celdas[i:]:
                if v == "" and n > 0:
                    break
                if v != "":
                    n += 1
            return n
        return 0

    @staticmethod
    def _quitar_citation(texto: str) -> str:
        """Las celdas de la ultima columna suelen traer pegado el texto
        del boton de cita ('... Citation: PROD - Error en X'); se recorta.

        Si la celda NO tenia texto de impacto propio (solo la cita), el
        resultado quedaria vacio -- se usa un texto de respaldo en vez de
        mandar una fila con ese campo en blanco."""
        resultado = texto.split("Citation:")[0].strip()
        return resultado if resultado else "(sin detalle adicional)"

    def copiar_tabla_de_respuesta(self) -> ResultadoCopilot:
        """Usa el boton 'Copy' REAL que Copilot pone sobre la tabla --
        solo existe en el arbol de accesibilidad mientras el mouse esta
        encima de la tarjeta de la respuesta (hover), por eso primero se
        mueve el cursor cerca de la tabla y se espera un momento.

        A proposito NO limpia ni reescribe el portapapeles despues de
        copiar: Copilot deja ahi tanto texto plano como HTML de la tabla
        real, y conservar el HTML es lo que permite que Teams la pegue
        como una tabla de verdad en vez de texto suelto.
        """
        tablas = self._ventana_copilot.descendants(control_type="Table")
        if not tablas:
            return ResultadoCopilot(tipo="error", contenido="", detalle={"motivo": "no hay tabla en la respuesta"})

        import pyautogui

        tabla = tablas[-1]
        rect = tabla.rectangle()
        x = rect.left + int((rect.right - rect.left) * 0.6)
        y = rect.top
        pyautogui.moveTo(x, y, duration=0.15)
        time.sleep(0.7)

        botones = self._ventana_copilot.descendants(control_type="Button")
        candidatos = [b for b in botones if b.window_text().strip() == "Copy"]
        if not candidatos:
            return ResultadoCopilot(
                tipo="error", contenido="", detalle={"motivo": "el botón 'Copy' no apareció tras el hover"}
            )

        candidatos[-1].invoke()
        time.sleep(1)
        contenido_plano = self._leer_portapapeles()
        self.logger.info("Tabla copiada de Copilot con el botón real (%d caracteres)", len(contenido_plano))
        return ResultadoCopilot(tipo="tabla", contenido=contenido_plano, detalle={})

    def esperar_tabla_de_respuesta(self, tiempo_maximo: float = 60, intervalo: float = 3) -> ResultadoCopilot:
        """Sondea leer_tabla_de_respuesta() hasta que aparezca una tabla
        o se agote tiempo_maximo -- para no adivinar cuanto tarda el
        agente en responder (varia bastante corrida a corrida)."""
        transcurrido = 0.0
        ultimo = ResultadoCopilot(tipo="error", contenido="", detalle={"motivo": "sin intentos"})
        while transcurrido < tiempo_maximo:
            ultimo = self.leer_tabla_de_respuesta()
            if ultimo.tipo == "tabla":
                return ultimo
            time.sleep(intervalo)
            transcurrido += intervalo
        self.logger.warning("Se agoto el tiempo de espera (%ss) sin obtener una tabla", tiempo_maximo)
        return ultimo

    def esperar_y_copiar_tabla(self, tiempo_maximo: float = 60, intervalo: float = 3) -> ResultadoCopilot:
        """Espera a que la tabla este lista (sondeo barato via
        leer_tabla_de_respuesta) y, en cuanto aparece, la copia con el
        botón real 'Copy' -- para conservar el formato de tabla real al
        pegarla despues en Teams, en vez de reconstruirla a mano."""
        listo = self.esperar_tabla_de_respuesta(tiempo_maximo=tiempo_maximo, intervalo=intervalo)
        if listo.tipo != "tabla":
            return listo
        return self.copiar_tabla_de_respuesta()

    def copiar_respuesta_completa(self) -> ResultadoCopilot:
        botones = self._ventana_copilot.descendants(control_type="Button")
        objetivo = next(b for b in botones if b.window_text().strip() == "Copy Response")
        objetivo.invoke()
        time.sleep(1)
        return ResultadoCopilot(tipo="texto", contenido=self._leer_portapapeles())

    # ---------- Microsoft Teams ----------

    def abrir_teams(self):
        """Busca por titulo (rapido) y confirma el PID contra el
        ejecutable real de Teams -- el titulo cambia segun el chat activo
        y puede coincidir por accidente con otra ventana (nos paso con
        una terminal cuyo titulo tambien decia 'Microsoft Teams')."""
        candidatos = findwindows.find_elements(title_re=".*Microsoft Teams.*")
        objetivo = next((c for c in candidatos if _proceso_de_ventana_es(c.process_id, EJECUTABLE_TEAMS)), None)
        if objetivo is None:
            raise RuntimeError("No se encontró una ventana de Microsoft Teams (ms-teams.exe) abierta")

        app = Application(backend="uia").connect(process=objetivo.process_id)
        self._ventana_teams = app.top_window()
        self._ventana_teams.set_focus()
        self.logger.info("Conectado a Microsoft Teams (pid=%s)", objetivo.process_id)
        return self._ventana_teams

    def abrir_chat_propio(self, correo: str, nombre_en_lista: str) -> bool:
        """Prefiere el chat ya existente en la lista (mas rapido y sin
        ambiguedad); si no esta ahi, lo busca por CORREO exacto -- nunca
        por nombre, para no confundir con alguien de nombre parecido."""
        items = self._ventana_teams.descendants(control_type="TreeItem")
        existente = next((i for i in items if i.window_text().strip() == f"Chat {nombre_en_lista}"), None)
        if existente is not None:
            existente.click_input()
            time.sleep(1.2)
            return True

        self._ventana_teams.type_keys("^n")
        time.sleep(1.5)
        self._ventana_teams.type_keys(correo, with_spaces=True, pause=0.03)
        time.sleep(2)

        items = self._ventana_teams.descendants(control_type="ListItem")
        resultado = next((i for i in items if correo.lower() in i.window_text().lower()), None)
        if resultado is None:
            self.logger.warning("No se encontro resultado de busqueda para %s", correo)
            return False
        resultado.click_input()
        time.sleep(1.2)
        return True

    def pegar_y_enviar(self, titulo_esperado: str, contenido_para_escribir: str | None = None) -> bool:
        """Limpia la caja, pega, y SOLO si el titulo de la ventana y el
        contenido pegado pasan la verificacion, envia. Si algo no cuadra
        en cualquier punto, se detiene sin enviar nada y devuelve False.

        Si `contenido_para_escribir` es None, usa lo que YA este en el
        portapapeles (ej. una tabla copiada de Copilot con formato rico)
        en vez de sobreescribirlo con texto plano -- en ese caso la
        verificacion es por COBERTURA de palabras, no texto exacto: Teams
        reescribe markdown/HTML al pegarlo (links, tablas) y el resultado
        nunca sera char-por-char igual al portapapeles aunque el pegado
        haya sido perfecto.
        """
        if titulo_esperado not in self._ventana_teams.window_text():
            self.logger.warning("Titulo no coincide antes de empezar -- no se toca la caja de mensaje")
            return False

        verificacion_exacta = contenido_para_escribir is not None
        if contenido_para_escribir is not None:
            self._escribir_portapapeles(contenido_para_escribir)
        esperado = self._leer_portapapeles()

        caja = self._caja_mensaje_teams()
        if not self._vaciar_caja(caja):
            self.logger.warning("No se pudo vaciar la caja de mensaje")
            return False

        caja.set_focus()
        time.sleep(0.2)
        caja.type_keys("^v")
        time.sleep(1.2)

        pegado = caja.window_text()
        titulo_ok = titulo_esperado in self._ventana_teams.window_text()

        if verificacion_exacta:
            normalizar = lambda s: " ".join(s.split())
            contenido_ok = normalizar(pegado) == normalizar(esperado)
        else:
            esperadas = self._palabras_significativas(esperado)
            pegadas = self._palabras_significativas(pegado)
            cobertura = len(esperadas & pegadas) / max(len(esperadas), 1)
            contenido_ok = cobertura >= 0.4 and len(pegado.strip()) > 30
            self.logger.info("Verificación de contenido (cobertura de palabras): %.0f%%", cobertura * 100)

        if not (contenido_ok and titulo_ok):
            self.logger.warning(
                "Verificacion final fallo (contenido_ok=%s, titulo_ok=%s) -- NO se envia", contenido_ok, titulo_ok
            )
            return False

        caja.set_focus()
        time.sleep(0.2)
        caja.type_keys("{ENTER}")
        time.sleep(1.5)
        self.logger.info("Mensaje enviado en Teams")
        return True

    @staticmethod
    def _palabras_significativas(texto: str) -> set[str]:
        """Tokens de 4+ caracteres, en minuscula -- para comparar
        contenido por cobertura de palabras en vez de texto exacto."""
        return {p.lower() for p in re.findall(r"[A-Za-zÀ-ÿ0-9_]{4,}", texto)}

    def _caja_mensaje_teams(self):
        ediciones = self._ventana_teams.descendants(control_type="Edit")
        return next(e for e in ediciones if (e.element_info.name or "").lower() == "type a message")

    @staticmethod
    def _vaciar_caja(caja, intentos: int = 3) -> bool:
        for _ in range(intentos):
            caja.set_focus()
            time.sleep(0.3)
            caja.type_keys("^a{DELETE}")
            time.sleep(0.4)
            if caja.window_text().strip() in ("", "Type a message"):
                return True
        return False

    # ---------- portapapeles ----------

    @staticmethod
    def _leer_portapapeles() -> str:
        win32clipboard.OpenClipboard()
        try:
            try:
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            except TypeError:
                return ""
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def _escribir_portapapeles(texto: str) -> None:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            if texto:
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, texto)
        finally:
            win32clipboard.CloseClipboard()


_MARCADOR_SIN_DATO = "(sin detalle adicional)"


def formatear_mensaje_teams(
    encabezado: list[str], filas: list[list[str]], titulo: str = "Fallas detectadas en PROD"
) -> str:
    """Convierte una tabla (encabezado + filas) en un mensaje legible para
    Teams -- generico a proposito: usa las etiquetas de columna REALES
    que trajo la tabla, nunca nombres fijos como 'Impacto', porque el
    agente no siempre arma la tabla con las mismas columnas (a veces la
    ultima es 'Impacto' con texto, otras veces es solo 'Evidencia' con un
    icono sin texto propio)."""
    bloques = []
    for i, fila in enumerate(filas, 1):
        pares = [(etq, val) for etq, val in zip(encabezado, fila) if val and val != _MARCADOR_SIN_DATO]
        if not pares:
            continue
        primera_etiqueta, primer_valor = pares[0]
        resto = "\n".join(f"   {etq}: {val}" for etq, val in pares[1:])
        bloque = f"{i}. {primer_valor}" if len(pares) == 1 else f"{i}. {primer_valor}\n{resto}"
        bloques.append(bloque)

    cuerpo = "\n\n".join(bloques) if bloques else "(sin filas)"
    return f"\U0001F4CB {titulo} — hoy\n\n{cuerpo}\n\n(Generado por el agente Monitor de Fallas)"


def crear_diccionario_de_acciones(instancia: CopilotTeamsActions) -> dict[str, Callable]:
    """Diccionario nombre->funcion para componer pasos por nombre, ej.
    ACCIONES['clickear_agente']('Monitor de Fallas')."""
    return {
        "abrir_copilot": instancia.abrir_copilot,
        "buscar_agente": instancia.buscar_agente,
        "clickear_agente": instancia.clickear_agente,
        "enviar_prompt": instancia.enviar_prompt,
        "leer_tabla_de_respuesta": instancia.leer_tabla_de_respuesta,
        "copiar_tabla_de_respuesta": instancia.copiar_tabla_de_respuesta,
        "esperar_tabla_de_respuesta": instancia.esperar_tabla_de_respuesta,
        "esperar_y_copiar_tabla": instancia.esperar_y_copiar_tabla,
        "copiar_respuesta_completa": instancia.copiar_respuesta_completa,
        "abrir_teams": instancia.abrir_teams,
        "abrir_chat_propio": instancia.abrir_chat_propio,
        "pegar_y_enviar": instancia.pegar_y_enviar,
    }
