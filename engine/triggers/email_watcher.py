"""Disparador tipo 'cuando llega un correo' via polling IMAP."""
from __future__ import annotations

import imaplib
import threading
import time
from typing import Callable


def observar_buzon(
    host: str,
    usuario: str,
    password: str,
    callback: Callable[[], None],
    carpeta: str = "INBOX",
    intervalo_seg: int = 30,
) -> threading.Thread:
    def _loop() -> None:
        visto = -1
        while True:
            with imaplib.IMAP4_SSL(host) as imap:
                imap.login(usuario, password)
                imap.select(carpeta)
                _, datos = imap.search(None, "UNSEEN")
                no_leidos = datos[0].split()
                if len(no_leidos) != visto and no_leidos:
                    visto = len(no_leidos)
                    callback()
            time.sleep(intervalo_seg)

    hilo = threading.Thread(target=_loop, daemon=True)
    hilo.start()
    return hilo
