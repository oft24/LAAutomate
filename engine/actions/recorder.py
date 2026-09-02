"""Grabadora de acciones web: inyecta un listener de JavaScript en el
navegador para capturar clicks y escritura mientras el usuario navega
manualmente (asi valida cada paso el mismo, en vivo), y convierte lo
grabado en codigo Python listo para correr con self.web -- igual que la
grabadora de flujos de escritorio/web de Power Automate, pero el
resultado es codigo editable, no un flujo binario.
"""
from __future__ import annotations

import re
import threading
import time

from engine.actions.web import WebActions

# Se ejecuta dentro de la pagina. Genera un selector CSS razonablemente
# estable para el elemento donde ocurrio el evento (prioriza id / atributos
# semanticos antes de caer a una ruta por posicion), y empuja el evento a
# un arreglo global que Python va vaciando por sondeo.
_SCRIPT_GRABADOR = r"""
(function() {
    if (window.__rpaGrabando) { return; }
    window.__rpaGrabando = true;

    // localStorage (no una variable de JS) porque sobrevive a la navegacion:
    // si el usuario da click y la pagina navega antes de que Python alcance
    // a leer el evento, una variable en memoria se perderia con el contexto
    // viejo -- localStorage del mismo origen sigue ahi en la pagina nueva.
    function leerEventos() {
        try { return JSON.parse(localStorage.getItem('__rpaEventos') || '[]'); }
        catch (e) { return []; }
    }
    function guardarEvento(evento) {
        var eventos = leerEventos();
        eventos.push(evento);
        localStorage.setItem('__rpaEventos', JSON.stringify(eventos));
    }

    function cssEscape(valor) {
        return String(valor).replace(/["\\]/g, '\\$&');
    }

    function selectorDe(el) {
        if (!el || el.nodeType !== 1) return null;
        if (el.id) return '#' + cssEscape(el.id);

        var atributos = ['data-testid', 'name', 'aria-label', 'placeholder'];
        for (var i = 0; i < atributos.length; i++) {
            var valor = el.getAttribute(atributos[i]);
            if (valor) {
                return el.tagName.toLowerCase() + '[' + atributos[i] + '="' + cssEscape(valor) + '"]';
            }
        }

        var partes = [];
        var nodo = el;
        var profundidad = 0;
        while (nodo && nodo.nodeType === 1 && profundidad < 6) {
            if (nodo.id) {
                partes.unshift('#' + cssEscape(nodo.id));
                break;
            }
            var etiqueta = nodo.tagName.toLowerCase();
            var padre = nodo.parentElement;
            if (padre) {
                var hermanosMismaEtiqueta = Array.prototype.filter.call(
                    padre.children, function(h) { return h.tagName === nodo.tagName; }
                );
                if (hermanosMismaEtiqueta.length > 1) {
                    etiqueta += ':nth-of-type(' + (hermanosMismaEtiqueta.indexOf(nodo) + 1) + ')';
                }
            }
            partes.unshift(etiqueta);
            nodo = padre;
            profundidad++;
        }
        return partes.join(' > ');
    }

    document.addEventListener('click', function(ev) {
        var sel = selectorDe(ev.target);
        if (!sel) return;
        guardarEvento({
            tipo: 'click',
            selector: sel,
            texto: (ev.target.innerText || '').trim().slice(0, 60)
        });
    }, true);

    // Tipos de <input> donde "el valor" no es texto tecleado sino un
    // estado (marcado/sin marcar, un archivo elegido, un color). Convertir
    // eso en self.web.escribir() produce codigo que no reproduce nada.
    var TIPOS_SIN_TEXTO = {
        checkbox: 1, radio: 1, file: 1, submit: 1, button: 1,
        image: 1, reset: 1, range: 1, color: 1
    };

    function esCampoDeTexto(el) {
        if (!el) return false;
        if (el.tagName === 'TEXTAREA') return true;
        if (el.tagName !== 'INPUT') return false;
        var tipo = (el.type || 'text').toLowerCase();
        return tipo !== 'password' && !TIPOS_SIN_TEXTO[tipo];
    }

    // Una escritura SUSTITUYE a la anterior sobre el mismo campo en vez de
    // encolarse: 'input' emite un evento por tecla y cada uno trae el valor
    // COMPLETO del campo, asi que guardarlos todos solo haria crecer el
    // JSON de localStorage (que se lee y reescribe entero en cada tecla)
    // para terminar quedandose igual con el ultimo.
    function guardarEscritura(evento) {
        var eventos = leerEventos();
        var ultimo = eventos[eventos.length - 1];
        if (ultimo && ultimo.tipo === 'escribir' && ultimo.selector === evento.selector) {
            eventos[eventos.length - 1] = evento;
        } else {
            eventos.push(evento);
        }
        localStorage.setItem('__rpaEventos', JSON.stringify(eventos));
    }

    // 'input' y no 'change': 'change' solo se emite cuando el campo CONFIRMA
    // su valor, que en un campo de texto significa al perder el foco. Quien
    // escribia y se iba directo a LaAutomate a presionar "Detener" nunca
    // sacaba el foco del campo dentro de la pagina, el evento no se emitia
    // nunca y el paso 'escribir' simplemente no existia -- el vaciado final
    // no puede recuperar un evento que el navegador jamas emitio. Era la
    // causa de que la grabadora web pareciera "no capturar lo que escribo".
    document.addEventListener('input', function(ev) {
        var el = ev.target;
        if (!esCampoDeTexto(el)) return;
        var sel = selectorDe(el);
        if (!sel) return;
        guardarEscritura({ tipo: 'escribir', selector: sel, valor: el.value });
    }, true);
})();
"""

_SONDEO_Y_LIMPIEZA = (
    "var e = []; try { e = JSON.parse(localStorage.getItem('__rpaEventos') || '[]'); } "
    "catch (err) {} localStorage.removeItem('__rpaEventos'); return e;"
)

_NOMBRE_VALIDO = re.compile(r"^[a-z][a-z0-9_]*$")

# Un comentario de Python termina en el primer salto de linea real -- si
# 'texto' (el innerText de lo que se clickeo, tomado tal cual de una pagina
# que puede no ser de confianza) trajera un salto de linea (via <br>,
# elementos de bloque, o CSS white-space:pre), lo que venga despues dejaria
# de ser comentario y se ejecutaria como codigo Python de verdad. Por eso
# nunca se inserta en el comentario sin pasar por esto primero.
_SALTOS_DE_LINEA = re.compile(r"[\r\n  ]+")


def _texto_seguro_para_comentario(texto: str) -> str:
    return _SALTOS_DE_LINEA.sub(" ", texto)


class GrabadoraWeb:
    """Envuelve un WebActions ya abierto para grabar clicks/escritura
    mientras el usuario interactua manualmente con la pagina."""

    def __init__(self, web_actions: WebActions, logger) -> None:
        self.web = web_actions
        self.logger = logger
        self.pasos: list[dict] = []
        self._grabando = False
        self._hilo: threading.Thread | None = None
        self._lock = threading.Lock()
        self.detencion_limpia = True
        # Ultima URL vista por el hilo de sondeo. La UI la lee para
        # mostrarla en vivo; NO puede preguntarle al driver por su cuenta
        # (serian dos hilos sobre la misma sesion de Selenium).
        self.url_actual: str | None = None

    def iniciar(self, url: str) -> None:
        self.pasos = [{"tipo": "ir_a", "url": url}]
        self.url_actual = url
        self.web.ir_a(url)
        self._registrar_auto_inyeccion()
        self._inyectar_en_pagina_actual()

        self._grabando = True
        self._hilo = threading.Thread(target=self._sondear, daemon=True)
        self._hilo.start()
        self.logger.info("Grabación iniciada en %s", url)

    def detener(self, tiempo_espera_hilo: float = 5.0) -> list[dict]:
        self._grabando = False
        if self._hilo:
            self._hilo.join(timeout=tiempo_espera_hilo)
            self.detencion_limpia = not self._hilo.is_alive()
        else:
            self.detencion_limpia = True

        if not self.detencion_limpia:
            # El hilo de sondeo sigue vivo (ej. una pagina con un dialogo
            # nativo alert()/confirm() abierto lo deja bloqueado dentro de
            # execute_script). NO tocamos el driver desde aqui: hacerlo
            # significaria dos hilos usando la misma sesion de Selenium a
            # la vez. El llamador debe evitar cerrar el navegador tambien.
            self.logger.warning(
                "El hilo de sondeo no respondió a tiempo -- se omite el flush final para no "
                "acceder al navegador desde dos hilos a la vez. Puede haber quedado abierto."
            )
            with self._lock:
                pasos = list(self.pasos)
            return pasos

        # Flush final: si el ultimo click del usuario ocurrio justo cuando el
        # hilo de sondeo estaba dormido (time.sleep), _grabando pasa a False
        # y el hilo sale sin volver a leer -- sin este flush esos eventos se
        # perderian en silencio.
        try:
            eventos_finales = self.web.driver.execute_script(_SONDEO_Y_LIMPIEZA) or []
        except Exception as exc:
            self.logger.debug("No se pudo hacer el flush final de eventos: %s", exc)
            eventos_finales = []

        with self._lock:
            if eventos_finales:
                self.pasos.extend(eventos_finales)
            pasos = list(self.pasos)

        self.logger.info("Grabación detenida: %d paso(s) capturados", len(pasos))
        return pasos

    def cancelar(self, tiempo_espera_hilo: float = 5.0) -> int:
        """Aborta la grabación, DESCARTA lo capturado y cierra el
        navegador. Devuelve cuántos pasos se tiraron.

        Se reusa detener() en vez de parar el hilo a mano porque toda la
        cautela de ahí sigue aplicando: si el sondeo quedó bloqueado en un
        alert()/confirm() nativo, tocar el driver desde este hilo serían
        dos hilos sobre la misma sesión de Selenium. Lo único que cambia
        es que el resultado se tira."""
        pasos = self.detener(tiempo_espera_hilo=tiempo_espera_hilo)
        with self._lock:
            self.pasos = []
        if self.detencion_limpia:
            try:
                self.web.cerrar()
            except Exception as exc:  # noqa: BLE001 - cancelar nunca debe reventar
                self.logger.debug("Error cerrando el navegador al cancelar: %s", exc)
        else:
            self.logger.warning(
                "Grabación cancelada pero el navegador quedó abierto (el hilo de sondeo seguía "
                "activo) -- ciérralo manualmente."
            )
        self.logger.info("Grabación cancelada por el usuario: %d paso(s) descartados", len(pasos))
        return len(pasos)

    def instantanea_de_pasos(self) -> list[dict]:
        """Copia de los pasos capturados hasta ahora, para mostrarlos en
        vivo. El hilo de sondeo extiende self.pasos bajo el mismo lock."""
        with self._lock:
            return [dict(p) for p in self.pasos]

    def _registrar_auto_inyeccion(self) -> None:
        """CDP: hace que el script se inyecte solo, automaticamente, en
        CUALQUIER pagina nueva que cargue de aqui en adelante -- se registra
        una sola vez por sesion de grabacion."""
        try:
            self.web.driver.execute_cdp_cmd("Page.enable", {})
            self.web.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument", {"source": _SCRIPT_GRABADOR}
            )
        except Exception as exc:
            self.logger.debug("CDP no disponible para auto-inyección: %s", exc)

    def _inyectar_en_pagina_actual(self) -> None:
        """Corre el script YA, en la pagina que este cargada en este momento.

        Se llama en cada ciclo de sondeo (no solo cuando se detecta un
        cambio de URL): si una pagina navega muy rapido, un intento de
        inyeccion puede caer justo a mitad de la transicion y fallar en
        silencio -- al reintentar cada ciclo, el siguiente intento (0.4s
        despues, con la pagina ya estable) lo corrige solo. El guard
        `window.__rpaGrabando` del propio script hace que reintentar sea
        gratis cuando ya habia quedado inyectado.
        """
        try:
            self.web.driver.execute_script(_SCRIPT_GRABADOR)
        except Exception as exc:
            self.logger.debug("No se pudo inyectar en la página actual: %s", exc)

    def _seguir_pestana_nueva(self, driver, handles_conocidos: set[str]) -> str | None:
        """Si apareció una pestaña que no existía, cambia a ella y devuelve
        su handle. Devuelve None si no hay ninguna nueva.

        Sin esto la grabación se rompía en silencio en cuanto un click abría
        una pestaña: el navegador se la muestra al usuario, que sigue
        trabajando ahí, pero el driver se queda apuntando a la pestaña vieja
        -- el sondeo seguía leyendo el localStorage de una página que ya
        nadie estaba tocando, así que ni el script se inyectaba en la
        pestaña nueva ni se capturaba un solo paso de todo lo que el usuario
        hiciera en ella. El resultado era una grabación que se cortaba justo
        donde el usuario creía que empezaba lo interesante.

        Cambiar el foco del driver aquí NO le estorba al usuario: la pestaña
        a la que se cambia es la que el navegador acaba de poner al frente
        por su cuenta, así que el driver solo se está poniendo al día.
        """
        nuevos = [h for h in driver.window_handles if h not in handles_conocidos]
        if not nuevos:
            return None
        handle = nuevos[-1]
        driver.switch_to.window(handle)
        return handle

    def _sondear(self) -> None:
        driver_inicial = self.web.driver
        url_anterior = driver_inicial.current_url
        handles_conocidos = set(driver_inicial.window_handles)
        while self._grabando:
            try:
                driver = self.web.driver

                # Leer los eventos ANTES de anotar cualquier cambio de
                # pagina o de pestaña: el click que provoco el cambio quedo
                # grabado en el localStorage de la pagina VIEJA. Si primero
                # anotaramos el "ir_a"/"cambiar_pestana", ese click
                # terminaria DESPUES en la secuencia generada, invertido
                # respecto a como paso en realidad -- y en el caso de la
                # pestaña ni siquiera llegaria: cambiar de pestaña primero
                # significa leer el localStorage de la pestaña nueva, que
                # esta vacio, y el click se pierde entero.
                eventos = driver.execute_script(_SONDEO_Y_LIMPIEZA) or []
                if eventos:
                    with self._lock:
                        self.pasos.extend(eventos)

                self._inyectar_en_pagina_actual()

                url_actual = driver.current_url
                self.url_actual = url_actual
                if url_actual != url_anterior:
                    with self._lock:
                        self.pasos.append({"tipo": "ir_a", "url": url_actual})
                    url_anterior = url_actual

                # Ya con los eventos de la pestaña anterior a salvo, se
                # sigue al usuario si abrio una pestaña nueva.
                if self._seguir_pestana_nueva(driver, handles_conocidos) is not None:
                    self._inyectar_en_pagina_actual()
                    # title/current_url se leen ANTES de tomar el lock: son
                    # viajes al navegador y el lock lo comparte el hilo que
                    # entrega los pasos en detener().
                    titulo, url_nueva = driver.title, driver.current_url
                    with self._lock:
                        self.pasos.append(
                            {"tipo": "cambiar_pestana", "titulo": titulo, "url": url_nueva}
                        )
                    url_anterior = url_nueva
                    self.url_actual = url_nueva
                # se recalcula SIEMPRE (no solo cuando se abrio una): asi una
                # pestaña cerrada sale del conjunto y, si el usuario vuelve
                # a abrir otra, se detecta como nueva igual.
                handles_conocidos = set(driver.window_handles)
            except Exception as exc:
                self.logger.debug("Sondeo de grabación interrumpido: %s", exc)
                return
            time.sleep(0.4)


def nombre_de_clase(nombre_automatizacion: str) -> str:
    return "".join(parte.capitalize() for parte in nombre_automatizacion.split("_"))


def validar_nombre(nombre: str) -> None:
    if not _NOMBRE_VALIDO.match(nombre):
        raise ValueError(
            "El nombre debe empezar con una letra minúscula y usar solo letras, números y guion bajo "
            "(ej. 'mi_proceso_web')."
        )


def _depurar_pasos(pasos: list[dict]) -> list[dict]:
    """Quita ruido de la grabación: navegaciones repetidas consecutivas y
    escritura duplicada sobre el mismo campo (nos quedamos solo con el
    ultimo valor tecleado antes del siguiente evento -- incluyendo un
    valor vacio, porque borrar un campo a proposito es una accion real,
    no ruido, y descartarla haria que se reproduzca un valor viejo que
    el usuario ya habia quitado)."""
    limpios: list[dict] = []
    for paso in pasos:
        if paso["tipo"] == "ir_a":
            if limpios and limpios[-1]["tipo"] == "ir_a" and limpios[-1]["url"] == paso["url"]:
                continue
            limpios.append(paso)
        elif paso["tipo"] == "escribir":
            if limpios and limpios[-1]["tipo"] == "escribir" and limpios[-1]["selector"] == paso["selector"]:
                limpios[-1] = paso  # se quedo el valor final tecleado, no cada tecla
            else:
                limpios.append(paso)
        elif paso["tipo"] == "cambiar_pestana":
            # dos cambios seguidos a la MISMA url son ruido del sondeo
            if (
                limpios
                and limpios[-1]["tipo"] == "cambiar_pestana"
                and limpios[-1].get("url") == paso.get("url")
            ):
                continue
            limpios.append(paso)
        elif paso["tipo"] == "click":
            limpios.append(paso)
    return limpios


def generar_codigo(nombre_automatizacion: str, pasos: list[dict]) -> str:
    """Traduce los pasos grabados a un automation.py real, usando repr()
    para insertar cada valor capturado como literal de Python -- así lo
    que el usuario haya escrito/clicado en la página (comillas, backslashes,
    lo que sea) queda como texto seguro, nunca como código ejecutable."""
    validar_nombre(nombre_automatizacion)
    clase = nombre_de_clase(nombre_automatizacion)

    lineas_cuerpo = []
    for paso in _depurar_pasos(pasos):
        if paso["tipo"] == "ir_a":
            lineas_cuerpo.append(f"        self.web.ir_a({paso['url']!r})")
        elif paso["tipo"] == "click":
            texto = _texto_seguro_para_comentario(paso["texto"]) if paso.get("texto") else ""
            comentario = f"  # {texto}" if texto else ""
            lineas_cuerpo.append(f"        self.web.click({paso['selector']!r}){comentario}")
        elif paso["tipo"] == "cambiar_pestana":
            # El click de la línea anterior abrió una pestaña. Se genera
            # cambiar_a_pestana_nueva() y no cambiar_a_pestana(indice): al
            # reproducir, el índice depende de cuántas pestañas hubiera
            # abiertas, que no es lo mismo que al grabar -- esperar "la que
            # no existía antes" sí se comporta igual en ambos momentos.
            titulo = _texto_seguro_para_comentario(paso.get("titulo") or "")
            comentario = f"  # {titulo}" if titulo else ""
            lineas_cuerpo.append(f"        self.web.cambiar_a_pestana_nueva(){comentario}")
        elif paso["tipo"] == "escribir":
            lineas_cuerpo.append(f"        self.web.escribir({paso['selector']!r}, {paso['valor']!r})")

    if not lineas_cuerpo:
        lineas_cuerpo.append("        pass  # no se capturó ningún paso durante la grabación")

    cuerpo = "\n".join(lineas_cuerpo)

    return (
        '"""Automatizacion generada por la Grabadora de clicks.\n\n'
        "Revisa cada paso antes de confiar en ella: los selectores se "
        "generan automaticamente y pueden necesitar ajuste si la pagina "
        'cambia.\n"""\n'
        "from __future__ import annotations\n\n"
        "from engine.automation_base import AutomationResult, BaseAutomation\n"
        "from engine.registry import registrar\n\n\n"
        f'@registrar(nombre={nombre_automatizacion!r}, disparador="manual", categoria="grabada")\n'
        f"class {clase}(BaseAutomation):\n"
        "    def ejecutar(self) -> AutomationResult:\n"
        f"{cuerpo}\n"
        "        return AutomationResult(success=True)\n"
    )
