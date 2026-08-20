"""Boveda de credenciales: usa el almacen de credenciales del sistema
(Windows Credential Manager via `keyring`), nunca texto plano en disco."""
from __future__ import annotations

from dataclasses import dataclass

import keyring

_SERVICIO = "rpa-code-platform"


@dataclass
class Credenciales:
    usuario: str | None = None
    password: str | None = None
    token: str | None = None


class Vault:
    def guardar(self, nombre: str, usuario: str, password: str) -> None:
        keyring.set_password(_SERVICIO, f"{nombre}:usuario", usuario)
        keyring.set_password(_SERVICIO, f"{nombre}:password", password)

    def guardar_token(self, nombre: str, token: str) -> None:
        keyring.set_password(_SERVICIO, f"{nombre}:token", token)

    def guardar_password(self, nombre: str, password: str) -> None:
        """Guarda SOLO la contraseña, sin tocar el usuario ya guardado (si
        lo hay) -- para el flujo de la Grabadora, que detecta que un campo
        de password se uso pero nunca captura ni conoce el usuario."""
        keyring.set_password(_SERVICIO, f"{nombre}:password", password)

    def guardar_usuario(self, nombre: str, usuario: str) -> None:
        """Guarda SOLO el usuario, sin tocar la contraseña/token ya
        guardados -- para editar el usuario de una credencial existente
        sin tener que volver a escribir (o peor, borrar por accidente al
        dejarlo vacío) la contraseña ya guardada."""
        keyring.set_password(_SERVICIO, f"{nombre}:usuario", usuario)

    def credenciales_para(self, nombre: str) -> Credenciales:
        return Credenciales(
            usuario=keyring.get_password(_SERVICIO, f"{nombre}:usuario"),
            password=keyring.get_password(_SERVICIO, f"{nombre}:password"),
            token=keyring.get_password(_SERVICIO, f"{nombre}:token"),
        )

    def tiene_credenciales(self, nombre: str) -> bool:
        """keyring (Windows Credential Manager) no ofrece una forma
        generica de LISTAR todas las claves guardadas -- por eso la UI no
        puede simplemente "enumerar la Boveda". En su lugar, se pregunta
        por cada automatizacion YA CONOCIDA (via engine.registry.listar())
        si tiene algo guardado, usando el mismo nombre exacto."""
        c = self.credenciales_para(nombre)
        return bool(c.usuario or c.password or c.token)

    def eliminar(self, nombre: str) -> None:
        for clave in ("usuario", "password", "token"):
            try:
                keyring.delete_password(_SERVICIO, f"{nombre}:{clave}")
            except keyring.errors.PasswordDeleteError:
                pass
