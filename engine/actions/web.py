"""Helpers de Selenium: esperas explicitas, reintentos y screenshot en error."""
from __future__ import annotations

import os
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
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

    @property
    def driver(self) -> webdriver.Chrome | webdriver.Edge:
        if self._driver is None:
            self._driver = self._abrir_navegador(self._navegador)
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
