"""Consulta el CURP de cada persona de un Excel y guarda su PDF en una carpeta.

Lee `datos/personas.xlsx`, consulta gob.mx/curp fila por fila, guarda el PDF
de cada persona en `datos/curps/` y escribe `datos/curps_resultado.xlsx` con
el CURP obtenido o el motivo del fallo.

LÉEME ANTES DE CONFIAR EN ESTO
------------------------------
La página carga reCAPTCHA Enterprise **invisible** (no es un "marca las
imágenes": puntúa el comportamiento del navegador). Un navegador
automatizado puntúa bajo, así que las consultas pueden empezar a fallar
después de unas cuantas filas. Esta automatización NO intenta esquivarlo:
va despacio, se detiene en cuanto detecta que la están bloqueando y te deja
reanudar. Para un lote grande, espera hacerlo en varias tandas.

Es reanudable: las filas que ya tienen su PDF en la carpeta destino se
saltan, así que volver a ejecutarla continúa donde se quedó.
"""
from __future__ import annotations

import time
import unicodedata
from pathlib import Path

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By

from core.config import BASE_DIR, var
from engine.automation_base import AutomationResult, BaseAutomation
from engine.registry import registrar

URL_CURP = "https://www.gob.mx/curp/"

# Rutas configurables desde el .env para no tocar el código al cambiarlas.
EXCEL_ENTRADA = Path(var("CURP_EXCEL", str(BASE_DIR / "datos" / "personas.xlsx")))
CARPETA_PDFS = Path(var("CURP_CARPETA", str(BASE_DIR / "datos" / "curps")))
EXCEL_SALIDA = CARPETA_PDFS.parent / "curps_resultado.xlsx"

# Segundos entre consultas. No es cortesía vacía: es lo que separa un uso
# razonable de un martilleo que el reCAPTCHA puntúa como robot.
PAUSA_ENTRE_CONSULTAS = float(var("CURP_PAUSA", "6"))

# Columnas que el Excel debe traer. Se comprueban ANTES de abrir el
# navegador: descubrir que falta "estado" en la fila 300, con 299 consultas
# ya gastadas contra un servicio con cuota, es el peor momento posible.
COLUMNAS = ("nombres", "primer_apellido", "segundo_apellido", "dia", "mes", "anio", "sexo", "estado")

# Identificadores reales del formulario, leídos de la página el 2026-09-04.
CAMPO_NOMBRES = "nombre"
CAMPO_PRIMER_APELLIDO = "primerApellido"
CAMPO_SEGUNDO_APELLIDO = "segundoApellido"
CAMPO_DIA = "diaNacimiento"
CAMPO_MES = "mesNacimiento"
CAMPO_ANIO = "selectedYear"
CAMPO_SEXO = "sexo"
CAMPO_ESTADO = "claveEntidad"
BOTON_BUSCAR = "searchButton"
PESTANA_DATOS = 'a[href="#tab-02"]'

# Sexo: la página usa H/M/X. Se acepta lo que la gente escribe de verdad en
# un Excel (M de "masculino" y M de "mujer" chocan, así que "m" a secas se
# rechaza en vez de adivinar y consultar a la persona equivocada).
SEXO = {
    "h": "H", "hombre": "H", "masculino": "H", "male": "H",
    "mujer": "M", "femenino": "M", "f": "M", "female": "M",
    "x": "X", "no binario": "X", "nobinario": "X",
}

# Entidad: se acepta la clave de 2 letras o el nombre del estado.
ENTIDADES = {
    "aguascalientes": "AS", "baja california": "BC", "baja california sur": "BS",
    "campeche": "CC", "coahuila": "CL", "colima": "CM", "chiapas": "CS",
    "chihuahua": "CH", "ciudad de mexico": "DF", "cdmx": "DF", "distrito federal": "DF",
    "durango": "DG", "guanajuato": "GT", "guerrero": "GR", "hidalgo": "HG",
    "jalisco": "JC", "estado de mexico": "MC", "mexico": "MC", "edomex": "MC",
    "michoacan": "MN", "morelos": "MS", "nayarit": "NT", "nuevo leon": "NL",
    "oaxaca": "OC", "puebla": "PL", "queretaro": "QT", "quintana roo": "QR",
    "san luis potosi": "SP", "sinaloa": "SL", "sonora": "SR", "tabasco": "TC",
    "tamaulipas": "TS", "tlaxcala": "TL", "veracruz": "VZ", "yucatan": "YN",
    "zacatecas": "ZS", "nacido en el extranjero": "NE", "extranjero": "NE",
}
CLAVES_ENTIDAD = set(ENTIDADES.values())


class DatosInvalidos(ValueError):
    """Una fila del Excel no se puede consultar tal como está escrita."""


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar(valor) -> str:
    """Texto limpio de una celda, tratando el vacio de Excel como vacio.

    Una celda vacia llega desde pandas como `float("nan")`, y `str(nan)`
    es la cadena "nan". Sin este filtro, esa palabra viaja como dato: la
    busqueda de YouTube acabo consultando literalmente "automatizacion con
    python nan", y en la del CURP se habria mandado "nan" como segundo
    apellido a un servicio oficial.
    """
    if valor is None:
        return ""
    # NaN es el unico valor que no es igual a si mismo.
    if isinstance(valor, float) and valor != valor:
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def clave_sexo(valor) -> str:
    crudo = normalizar(valor).lower()
    clave = SEXO.get(crudo)
    if clave is None:
        raise DatosInvalidos(
            f"sexo {valor!r} no reconocido. Usa Hombre/Mujer/No binario o H/M/X "
            "(«M» a secas es ambiguo entre masculino y mujer, por eso no se acepta)."
        )
    return clave


def clave_entidad(valor) -> str:
    crudo = normalizar(valor)
    if crudo.upper() in CLAVES_ENTIDAD:
        return crudo.upper()
    clave = ENTIDADES.get(_sin_acentos(crudo).lower())
    if clave is None:
        raise DatosInvalidos(
            f"estado {valor!r} no reconocido. Usa el nombre del estado o su clave de 2 letras "
            "(ej. «Jalisco» o «JC»; «NE» para nacido en el extranjero)."
        )
    return clave


def dos_digitos(valor, campo: str, minimo: int, maximo: int) -> str:
    """El formulario espera '01', no '1': un 1 suelto no hace match con
    ninguna opción del <select> y Selenium falla sin decir por qué."""
    crudo = normalizar(valor)
    try:
        numero = int(float(crudo))  # float: pandas puede leer 5 como 5.0
    except (TypeError, ValueError):
        raise DatosInvalidos(f"{campo} {valor!r} no es un número.") from None
    if not minimo <= numero <= maximo:
        raise DatosInvalidos(f"{campo} {numero} fuera de rango ({minimo}-{maximo}).")
    return f"{numero:02d}"


def anio_valido(valor) -> str:
    crudo = normalizar(valor)
    try:
        numero = int(float(crudo))
    except (TypeError, ValueError):
        raise DatosInvalidos(f"anio {valor!r} no es un número.") from None
    if not 1900 <= numero <= 2100:
        raise DatosInvalidos(f"anio {numero} fuera de rango (1900-2100).")
    return str(numero)


def nombre_archivo(fila: dict) -> str:
    """Nombre de archivo estable y sin caracteres prohibidos en Windows.

    Estable importa: es lo que permite reanudar -- si el PDF ya existe, esa
    fila ya se consultó y se salta.
    """
    partes = [
        normalizar(fila.get("primer_apellido")),
        normalizar(fila.get("segundo_apellido")),
        normalizar(fila.get("nombres")),
    ]
    base = "_".join(p for p in partes if p)
    limpio = "".join(c if c.isalnum() or c in " _-" else "_" for c in _sin_acentos(base))
    return "_".join(limpio.split()).lower() or "sin_nombre"


@registrar(nombre="curp_desde_excel", disparador="manual", categoria="tramites")
class CurpDesdeExcel(BaseAutomation):
    def ejecutar(self) -> AutomationResult:
        if not EXCEL_ENTRADA.exists():
            raise FileNotFoundError(
                f"No encuentro {EXCEL_ENTRADA}. Genera la plantilla con "
                "`python tools/plantilla_curp.py` o define CURP_EXCEL en el .env."
            )

        filas = self.excel.leer(EXCEL_ENTRADA)
        if not filas:
            return AutomationResult(success=True, message="El Excel no tiene filas.")

        faltantes = [c for c in COLUMNAS if c not in filas[0]]
        if faltantes:
            raise DatosInvalidos(
                f"Al Excel le faltan columnas: {', '.join(faltantes)}. "
                f"Se esperan exactamente: {', '.join(COLUMNAS)}."
            )

        CARPETA_PDFS.mkdir(parents=True, exist_ok=True)
        # Antes de abrir el navegador: Chrome fija la carpeta de descargas
        # al arrancar y no la relee.
        self.web.descargar_en(CARPETA_PDFS)

        resultados: list[dict] = []
        consultadas = saltadas = fallidas = 0

        for numero, fila in enumerate(filas, start=2):  # 2 = primera fila de datos en el Excel
            etiqueta = nombre_archivo(fila)
            pdf_esperado = CARPETA_PDFS / f"{etiqueta}.pdf"

            if pdf_esperado.exists():
                saltadas += 1
                self.logger.info("Fila %s (%s): ya tenía PDF, se salta", numero, etiqueta)
                resultados.append({**fila, "curp": "", "estado_consulta": "ya existía", "pdf": pdf_esperado.name})
                continue

            try:
                datos = self._validar(fila)
            except DatosInvalidos as exc:
                fallidas += 1
                self.logger.error("Fila %s (%s): %s", numero, etiqueta, exc)
                resultados.append({**fila, "curp": "", "estado_consulta": f"datos inválidos: {exc}", "pdf": ""})
                continue

            try:
                curp = self._consultar(datos)
            except _PosibleBloqueo as exc:
                # Se para en seco: seguir insistiendo empeora la puntuación
                # del reCAPTCHA y quema el resto del lote.
                self.logger.error("Fila %s: %s", numero, exc)
                resultados.append({**fila, "curp": "", "estado_consulta": str(exc), "pdf": ""})
                self._guardar_resultados(resultados)
                return AutomationResult(
                    success=False,
                    message=(
                        f"Detenida en la fila {numero}: {exc} Ya se guardaron {consultadas} CURP. "
                        "Espera un rato y vuelve a ejecutarla: continuará donde se quedó."
                    ),
                    data={"consultadas": consultadas, "saltadas": saltadas, "fallidas": fallidas},
                )
            except Exception as exc:  # noqa: BLE001 - una fila mala no debe tumbar el lote entero
                fallidas += 1
                self.logger.exception("Fila %s (%s) falló", numero, etiqueta)
                resultados.append({**fila, "curp": "", "estado_consulta": f"{type(exc).__name__}: {exc}", "pdf": ""})
                continue

            pdf = self._descargar_pdf(pdf_esperado)
            consultadas += 1
            resultados.append(
                {
                    **fila,
                    "curp": curp,
                    "estado_consulta": "ok" if pdf else "CURP obtenido, PDF no descargado",
                    "pdf": pdf.name if pdf else "",
                }
            )
            self.logger.info("Fila %s (%s): %s", numero, etiqueta, curp)
            time.sleep(PAUSA_ENTRE_CONSULTAS)

        self._guardar_resultados(resultados)
        return AutomationResult(
            success=fallidas == 0,
            message=f"{consultadas} consultadas, {saltadas} ya existían, {fallidas} con error.",
            data={"consultadas": consultadas, "saltadas": saltadas, "fallidas": fallidas,
                  "salida": str(EXCEL_SALIDA)},
        )

    # ------------------------------------------------------------ pasos

    def _validar(self, fila: dict) -> dict:
        """Traduce una fila del Excel a lo que el formulario espera.

        Se valida TODO antes de tocar la red: una fila con el estado mal
        escrito no debe gastar una consulta para descubrirlo.
        """
        nombres = normalizar(fila.get("nombres"))
        primer = normalizar(fila.get("primer_apellido"))
        if not nombres or not primer:
            raise DatosInvalidos("faltan nombres o primer apellido.")
        return {
            "nombres": nombres,
            "primer_apellido": primer,
            "segundo_apellido": normalizar(fila.get("segundo_apellido")),
            "dia": dos_digitos(fila.get("dia"), "dia", 1, 31),
            "mes": dos_digitos(fila.get("mes"), "mes", 1, 12),
            "anio": anio_valido(fila.get("anio")),
            "sexo": clave_sexo(fila.get("sexo")),
            "estado": clave_entidad(fila.get("estado")),
        }

    def _consultar(self, datos: dict) -> str:
        self.web.ir_a(URL_CURP)
        self._cerrar_aviso()
        self.web.click(PESTANA_DATOS)

        self.web.escribir(CAMPO_NOMBRES, datos["nombres"], by=By.ID)
        self.web.escribir(CAMPO_PRIMER_APELLIDO, datos["primer_apellido"], by=By.ID)
        if datos["segundo_apellido"]:
            self.web.escribir(CAMPO_SEGUNDO_APELLIDO, datos["segundo_apellido"], by=By.ID)
        self.web.seleccionar(CAMPO_DIA, valor=datos["dia"], by=By.ID)
        self.web.seleccionar(CAMPO_MES, valor=datos["mes"], by=By.ID)
        self.web.escribir(CAMPO_ANIO, datos["anio"], by=By.ID)
        self.web.seleccionar(CAMPO_SEXO, valor=datos["sexo"], by=By.ID)
        self.web.seleccionar(CAMPO_ESTADO, valor=datos["estado"], by=By.ID)
        self.web.click(BOTON_BUSCAR, by=By.ID)

        return self._leer_curp()

    def _cerrar_aviso(self) -> None:
        """La página abre un modal de aviso que tapa el formulario."""
        try:
            self.web.click("button.btn-default", by=By.CSS_SELECTOR)
        except (TimeoutException, WebDriverException):
            pass  # no siempre aparece; que no esté no es un fallo

    def _leer_curp(self) -> str:
        """Saca el CURP del resultado, o dice por qué no lo hay.

        El CURP se busca por su PATRÓN (18 caracteres con una forma fija)
        en el texto de la página, no con un selector: el bloque de
        resultado cambia de estructura, pero un CURP siempre se ve igual.

        El error, en cambio, sí tiene sitio fijo: la página lo pinta en un
        `div.alert-danger`. Se comprobó enviando datos imposibles y
        responde, por ejemplo, «El campo primer apellido: No cumple con el
        formato especificado.». Antes se leía el body entero buscando "no
        se encontró" —texto que la página nunca usa—, así que cualquier
        fallo se reportaba como «¿cambió la página?»: el peor mensaje
        posible, porque acusa a la herramienta cuando el problema está en
        el dato.
        """
        import re

        time.sleep(1.5)  # el resultado llega por AJAX
        texto = self.web.driver.find_element(By.TAG_NAME, "body").text

        encontrado = re.search(r"\b[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d\b", texto)
        if encontrado:
            return encontrado.group(0)

        aviso = self._mensaje_de_error()
        if aviso:
            bajo = aviso.lower()
            if "recaptcha" in bajo or "robot" in bajo or "intenta" in bajo and "tarde" in bajo:
                raise _PosibleBloqueo(f"la página respondió con una verificación anti-robot: {aviso}")
            # Lo devuelve tal cual: el mensaje de la propia página ("No
            # cumple con el formato especificado", "No se encontró...")
            # es más útil que cualquier parafraseo nuestro.
            raise ValueError(f"la página rechazó la consulta: {aviso}")

        raise ValueError(
            "no apareció ningún CURP ni mensaje de error. Puede que el envío se haya descartado "
            "en silencio (reCAPTCHA) o que la página haya cambiado."
        )

    def _mensaje_de_error(self) -> str:
        """El texto del aviso rojo que la página muestra al rechazar.

        Se filtran los `alert-info` a propósito: la página tiene dos fijos
        (la sugerencia del teléfono y el aviso de privacidad) que están
        SIEMPRE, y tomarlos por un error diría que la consulta falló en
        todas las filas.
        """
        try:
            avisos = self.web.driver.find_elements(By.CSS_SELECTOR, "div.alert-danger, .text-danger")
        except WebDriverException:
            return ""
        for aviso in avisos:
            try:
                if aviso.is_displayed() and aviso.text.strip():
                    return " ".join(aviso.text.split())[:300]
            except WebDriverException:
                continue
        return ""

    def _descargar_pdf(self, destino: Path) -> Path | None:
        """Pulsa «Descargar» y renombra el PDF al nombre estable de la fila.

        Devuelve None si no llegó: quedarse sin PDF no invalida el CURP ya
        obtenido, y el Excel de salida lo deja anotado.
        """
        try:
            self.web.click("//a[contains(., 'Descargar') or contains(., 'descargar')]", by=By.XPATH)
        except (TimeoutException, WebDriverException):
            self.logger.info("No había botón de descarga para %s", destino.stem)
            return None

        descargado = self.web.esperar_descarga(CARPETA_PDFS, ".pdf", timeout=30)
        if descargado is None:
            self.logger.info("La descarga de %s no llegó a tiempo", destino.stem)
            return None
        try:
            return descargado.replace(destino)
        except OSError:
            return descargado  # el nombre original sirve; no se pierde el archivo

    def _guardar_resultados(self, resultados: list[dict]) -> None:
        """Se escribe también cuando el lote se corta: si solo se guardara
        al final, un bloqueo a mitad tiraría el trabajo ya hecho."""
        if resultados:
            self.excel.escribir(EXCEL_SALIDA, resultados, hoja="curps")
            self.logger.info("Resultados en %s", EXCEL_SALIDA)


class _PosibleBloqueo(RuntimeError):
    """El servicio dejó de responder con datos: parece anti-robot."""
