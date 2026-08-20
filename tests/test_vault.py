from core.vault import Vault

_NOMBRE_PRUEBA = "pytest_vault_check"


def test_guardar_y_leer_credenciales() -> None:
    vault = Vault()
    try:
        vault.guardar(_NOMBRE_PRUEBA, usuario="usuario_prueba", password="clave_prueba")

        credenciales = vault.credenciales_para(_NOMBRE_PRUEBA)

        assert credenciales.usuario == "usuario_prueba"
        assert credenciales.password == "clave_prueba"
    finally:
        vault.eliminar(_NOMBRE_PRUEBA)


def test_guardar_password_no_toca_el_usuario_ya_guardado() -> None:
    vault = Vault()
    try:
        vault.guardar(_NOMBRE_PRUEBA, usuario="usuario_prueba", password="clave_vieja")

        vault.guardar_password(_NOMBRE_PRUEBA, "clave_nueva")

        credenciales = vault.credenciales_para(_NOMBRE_PRUEBA)
        assert credenciales.usuario == "usuario_prueba"
        assert credenciales.password == "clave_nueva"
    finally:
        vault.eliminar(_NOMBRE_PRUEBA)


def test_guardar_usuario_no_toca_la_password_ya_guardada() -> None:
    vault = Vault()
    try:
        vault.guardar(_NOMBRE_PRUEBA, usuario="usuario_viejo", password="clave_prueba")

        vault.guardar_usuario(_NOMBRE_PRUEBA, "usuario_nuevo")

        credenciales = vault.credenciales_para(_NOMBRE_PRUEBA)
        assert credenciales.usuario == "usuario_nuevo"
        assert credenciales.password == "clave_prueba"
    finally:
        vault.eliminar(_NOMBRE_PRUEBA)


def test_credenciales_inexistentes_devuelven_none() -> None:
    vault = Vault()
    credenciales = vault.credenciales_para("automatizacion_que_no_existe")

    assert credenciales.usuario is None
    assert credenciales.password is None
