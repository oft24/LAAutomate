"""Helpers de Selenium: esperas explicitas, reintentos y screenshot en error."""
from __future__ import annotations

import os
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCREENSHOTS_DIR = Path("logs/screenshots")


class WebActions:
    """Navegador Selenium. Muchos equipos corporativos no tienen Chrome
    instalado pero sí Edge (viene con Windows) — por eso el modo por
    defecto "auto" prueba Chrome y cae a Edge si no lo encuentra."""

    def __init__(self, logger, headless: bool = False, timeout: int = 15, navegador: str | None = None) -> None:
        self.logger = logger
        self.timeout = timeout
        self._driver: webdriver.Chrome | webdriver.Edge | None = None
        self._headless = headless
        self._navegador = navegador or os.getenv("RPA_NAVEGADOR", "auto")
        # Pestañas vistas en la última operación de pestañas. Es la
        # referencia de qué cuenta como "pestaña nueva" -- ver
        # cambiar_a_pestana_nueva().
        self._handles_conocidos: set[str] = set()

    @property
    def driver(self) -> webdriver.Chrome | webdriver.Edge:
        if self._driver is None:
            self._driver = self._abrir_navegador(self._navegador)
            self._handles_conocidos = set(self._driver.window_handles)
        return self._driver

    def _abrir_navegador(self, navegador: str) -> webdriver.Chrome | webdriver.Edge:
        if navegador == "edge":
            return self._abrir_edge()
        if navegador == "chrome":
            return self._abrir_chrome()
        try:
            return self._abrir_chrome()
        except WebDriverException:
            self.logger.info("Chrome no disponible, usando Edge")
            return self._abrir_edge()

    def _abrir_chrome(self) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        return webdriver.Chrome(options=options)

    def _abrir_edge(self) -> webdriver.Edge:
        options = webdriver.EdgeOptions()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        return webdriver.Edge(options=options)

    def _recordar_pestanas(self) -> None:
        """Fija la foto de pestañas contra la que se comparará la próxima
        búsqueda de una pestaña nueva."""
        try:
            self._handles_conocidos = set(self.driver.window_handles)
        except WebDriverException:
            self._handles_conocidos = set()

    def _wait(self) -> WebDriverWait:
        return WebDriverWait(self.driver, self.timeout)

    def ir_a(self, url: str) -> None:
        self.logger.info("Navegando a %s", url)
        self.driver.get(url)

    def click(self, selector: str, by: str = By.CSS_SELECTOR) -> None:
        el = self._wait().until(EC.element_to_be_clickable((by, selector)))
        el.click()

    def escribir(self, selector: str, texto: str, by: str = By.CSS_SELECTOR) -> None:
        el = self._wait().until(EC.visibility_of_element_located((by, selector)))
        el.clear()
        el.send_keys(texto)

    def leer_texto(self, selector: str, by: str = By.CSS_SELECTOR) -> str:
        el = self._wait().until(EC.visibility_of_element_located((by, selector)))
        return el.text

    # ---------------------------- pestañas ----------------------------
    #
    # Selenium NO sigue a una pestaña nueva por su cuenta. Cuando un click
    # abre una pestaña (target="_blank", window.open, un "Abrir en pestaña
    # nueva"), el navegador la muestra al usuario pero el driver se queda
    # apuntando a la pestaña VIEJA: los pasos siguientes se ejecutan contra
    # la página anterior y fallan con NoSuchElementException -- o peor,
    # encuentran un elemento homónimo y hacen algo en la página equivocada,
    # sin error. Todo cambio de pestaña tiene que ser explícito.

    def pestanas(self) -> list[str]:
        """Títulos de las pestañas abiertas, en el orden del navegador.

        Leer el título de una pestaña obliga a cambiarse a ella (Selenium
        solo expone `title` de la pestaña activa), así que este método
        recorre todas y **regresa el foco a donde estaba**. Si la pestaña
        activa se había cerrado, deja el foco en la última que quede en vez
        de dejar el driver sin ventana válida.
        """
        handles = self.driver.window_handles
        try:
            handle_original = self.driver.current_window_handle
        except WebDriverException:
            handle_original = None

        titulos = []
        for handle in handles:
            self.driver.switch_to.window(handle)
            titulos.append(self.driver.title)

        if handle_original in handles:
            self.driver.switch_to.window(handle_original)
        elif handles:
            self.driver.switch_to.window(handles[-1])
        return titulos

    def cambiar_a_pestana(self, referencia: int | str) -> str:
        """Pone el foco en otra pestaña y devuelve su título.

        `referencia` puede ser el índice (0 es la primera) o un fragmento
        del título o de la URL, sin distinguir mayúsculas -- buscar por
        texto es lo que sobrevive a que el orden cambie entre corridas:
        el índice de una pestaña depende de en qué orden se abrieron, que
        no es estable cuando la app abre pestañas sola.
        """
        handles = self.driver.window_handles

        if isinstance(referencia, int):
            if not -len(handles) <= referencia < len(handles):
                raise LookupError(
                    f"No existe la pestaña {referencia}: hay {len(handles)} abierta(s). "
                    f"Títulos actuales: {self.pestanas()}"
                )
            self.driver.switch_to.window(handles[referencia])
            self._recordar_pestanas()
            self.logger.info("Cambiado a la pestaña %s (%s)", referencia, self.driver.title)
            return self.driver.title

        # El handle de partida se guarda ANTES del barrido: buscar obliga a
        # cambiarse a cada pestaña, así que si ninguna coincide hay que
        # devolver el foco a mano -- si no, un LookupError capturado por la
        # automatización la dejaría trabajando en la última pestaña que la
        # búsqueda visitó, que no es donde estaba.
        try:
            handle_original = self.driver.current_window_handle
        except WebDriverException:
            handle_original = None

        buscado = referencia.lower()
        titulos = []
        for handle in handles:
            self.driver.switch_to.window(handle)
            titulos.append(self.driver.title)
            if buscado in self.driver.title.lower() or buscado in self.driver.current_url.lower():
                self._recordar_pestanas()
                self.logger.info("Cambiado a la pestaña %r (%s)", referencia, self.driver.title)
                return self.driver.title

        if handle_original in handles:
            self.driver.switch_to.window(handle_original)
        elif handles:
            self.driver.switch_to.window(handles[-1])
        raise LookupError(
            f"Ninguna pestaña abierta coincide con {referencia!r}. Títulos actuales: {titulos}"
        )

    def cambiar_a_pestana_nueva(self, timeout: float | None = None) -> str:
        """Espera a que aparezca una pestaña que no existía y cambia a ella.

        Es el método a usar justo DESPUÉS del click que abre una pestaña.
        Espera de verdad (no `time.sleep`) porque la pestaña tarda en
        registrarse: preguntar por `window_handles` inmediatamente después
        del click suele devolver todavía la lista vieja, y quedarse en la
        pestaña anterior es precisamente el fallo silencioso que este
        bloque de métodos existe para evitar.
        """
        # Se compara contra las pestañas que WebActions YA conocía, no
        # contra una foto tomada en esta misma línea: la pestaña suele
        # abrirse durante el click anterior, así que para cuando se llama a
        # este método normalmente ya existe. Fotografiarla aquí la daría por
        # "vieja" y el método esperaría en vano una SEGUNDA pestaña que
        # nunca llega. El conjunto conocido se refresca en cada operación de
        # pestañas, así que "nueva" significa "apareció desde la última vez
        # que miramos a propósito" -- que es lo que se quiere decir.
        conocidas = self._handles_conocidos
        actual = self.driver.current_window_handle

        def aparecio_una_nueva(driver):
            nuevas = [h for h in driver.window_handles if h not in conocidas]
            return nuevas[-1] if nuevas else False

        espera = WebDriverWait(self.driver, timeout if timeout is not None else self.timeout)
        try:
            handle_nuevo = espera.until(aparecio_una_nueva)
        except TimeoutException:
            self.driver.switch_to.window(actual)
            raise TimeoutError(
                f"No se abrió ninguna pestaña nueva en {timeout or self.timeout}s. "
                "¿El click de antes realmente abre una pestaña? Si abre la misma, "
                "no hace falta cambiar de pestaña."
            ) from None

        self.driver.switch_to.window(handle_nuevo)
        self._recordar_pestanas()
        self.logger.info("Cambiado a la pestaña nueva (%s)", self.driver.title)
        return self.driver.title

    def nueva_pestana(self, url: str | None = None) -> None:
        """Abre una pestaña nueva, cambia el foco a ella y opcionalmente
        navega. Útil para trabajar dos sistemas en paralelo (ej. leer un
        dato en un portal y capturarlo en otro) sin perder la sesión de
        ninguno: dos pestañas del mismo navegador comparten las cookies,
        dos navegadores distintos no."""
        self.driver.switch_to.new_window("tab")
        self._recordar_pestanas()
        if url:
            self.ir_a(url)
        self.logger.info("Pestaña nueva abierta%s", f" en {url}" if url else "")

    def cerrar_pestana(self) -> None:
        """Cierra la pestaña actual y deja el foco en la última que quede.

        Reposicionar el foco no es opcional: tras un `close()` el driver se
        queda sin ventana válida y CUALQUIER comando siguiente revienta con
        NoSuchWindowException, aunque el navegador siga abierto con otras
        pestañas a la vista. Si era la única, se cierra el navegador entero
        para no dejar un proceso huérfano.
        """
        self.driver.close()
        restantes = self.driver.window_handles
        if not restantes:
            # close() sobre la última ventana termina el navegador, pero NO
            # el proceso del driver: sin quit() queda un chromedriver/
            # msedgedriver huérfano. El runner tampoco lo recogería, porque
            # su cerrar() del final ve _driver ya en None y no hace nada.
            self.logger.info("Se cerró la última pestaña -- el navegador queda cerrado")
            try:
                self._driver.quit()
            except Exception as exc:  # noqa: BLE001 - cerrar nunca debe reventar
                self.logger.debug("Error cerrando el driver tras la última pestaña: %s", exc)
            self._driver = None
            self._handles_conocidos = set()
            return
        self.driver.switch_to.window(restantes[-1])
        self._recordar_pestanas()
        self.logger.info("Pestaña cerrada; foco en %r", self.driver.title)

    def screenshot_error(self, nombre_automatizacion: str) -> Path | None:
        if self._driver is None:
            return None
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        ruta = SCREENSHOTS_DIR / f"{nombre_automatizacion}_error.png"
        self._driver.save_screenshot(str(ruta))
        self.logger.info("Screenshot de error guardado en %s", ruta)
        return ruta

    def cerrar(self) -> None:
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
