"""La memoria del autocorrector, y que sobreviva a una actualización.

Son dos archivos: el que trae la versión (dentro de `_internal/`, que el
instalador borra y recrea) y el que aprende esta instalación (junto al
ejecutable). Tenerlo todo en uno obligaba a elegir, al actualizar, entre
perder lo aprendido o perder lo que traía la versión nueva.
"""
from __future__ import annotations


# ------------------------------- la memoria sobrevive a una actualizacion


def test_en_desarrollo_sigue_siendo_un_solo_archivo() -> None:
    """Partir en dos un repositorio que git ya versiona no aporta nada."""
    from engine import practicas

    assert practicas.ruta() == practicas.ruta_base()


def test_empaquetada_escribe_fuera_de_internal(monkeypatch, tmp_path) -> None:
    """`_internal/` lo borra el instalador en cada actualización: escribir
    ahí es perder lo aprendido en la siguiente versión. Se comprobó en vivo.
    """
    import sys

    from engine import practicas

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(practicas, "BASE_DIR", tmp_path)

    destino = practicas.ruta()

    assert destino.parent == tmp_path, "debe quedar junto al ejecutable"
    assert "_internal" not in str(destino)
    assert destino.name == "practicas_aprendidas.md"


def test_se_leen_las_dos_memorias_juntas(monkeypatch, tmp_path) -> None:
    from engine import practicas

    base = tmp_path / "PRACTICAS.md"
    base.write_text(
        "# Base\n\n"
        f"{practicas.MARCA_INICIO}\n\n- **v1** — regla que trae la versión\n\n"
        f"{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    propias = tmp_path / "practicas_aprendidas.md"
    propias.write_text(
        f"# Aprendidas\n\n{practicas.MARCA_INICIO}\n\n"
        "- **hoy** — regla que aprendió este equipo\n\n"
        f"{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(practicas, "ruta_base", lambda: base)
    monkeypatch.setattr(practicas, "ruta", lambda: propias)

    texto = practicas.leer()

    assert "regla que trae la versión" in texto
    assert "regla que aprendió este equipo" in texto


def test_la_primera_practica_crea_el_archivo_propio(monkeypatch, tmp_path) -> None:
    from engine import practicas

    base = tmp_path / "PRACTICAS.md"
    base.write_text(
        f"# Base\n\n{practicas.MARCA_INICIO}\n\n{practicas.MARCA_FIN}\n", encoding="utf-8"
    )
    propias = tmp_path / "practicas_aprendidas.md"
    monkeypatch.setattr(practicas, "ruta_base", lambda: base)
    monkeypatch.setattr(practicas, "ruta", lambda: propias)

    assert not propias.exists()
    assert practicas.anotar("Espera a que el elemento exista antes de pulsarlo.", "mi_auto")

    assert propias.exists()
    assert "Espera a que el elemento exista" in propias.read_text(encoding="utf-8")
    assert "Espera a que el elemento exista" not in base.read_text(encoding="utf-8"), (
        "la memoria aprendida no debe escribirse en el archivo del paquete"
    )


def test_no_se_repite_una_regla_que_ya_trae_la_version(monkeypatch, tmp_path) -> None:
    from engine import practicas

    base = tmp_path / "PRACTICAS.md"
    base.write_text(
        f"# Base\n\n{practicas.MARCA_INICIO}\n\n"
        "- **v1** — En un campo de texto usa click_por_tipo('Edit'), nunca su contenido.\n\n"
        f"{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    propias = tmp_path / "practicas_aprendidas.md"
    monkeypatch.setattr(practicas, "ruta_base", lambda: base)
    monkeypatch.setattr(practicas, "ruta", lambda: propias)

    guardada = practicas.anotar(
        "Usa click_por_tipo('Edit') en un campo de texto y nunca su contenido.", "otra"
    )

    assert not guardada, "ya está escrita en las que trae la versión"


# --------------------------------------------------------- la mudanza


def test_lo_aprendido_antes_se_muda_solo(monkeypatch, tmp_path) -> None:
    """Una instalación anterior las guardaba dentro de `_internal/`. El
    instalador deja ese archivo aparte y la app lo muda al arrancar.

    El archivo del paquete NO se toca: restaurarlo encima perdía las
    prácticas nuevas que trajera la versión. Pasó de verdad.
    """
    from engine import practicas

    base = tmp_path / "PRACTICAS.md"
    base.write_text(
        f"# Base\n\n{practicas.MARCA_INICIO}\n\n"
        "- **v2** — práctica que trae la versión nueva\n\n"
        f"{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    viejo = tmp_path / "practicas_por_migrar.md"
    viejo.write_text(
        f"# Viejo\n\n{practicas.MARCA_INICIO}\n\n"
        "- **ayer** — lo que este equipo ya había aprendido\n"
        "- **ayer** — y esta otra regla también\n\n"
        f"{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    propias = tmp_path / "practicas_aprendidas.md"
    monkeypatch.setattr(practicas, "ruta_base", lambda: base)
    monkeypatch.setattr(practicas, "ruta", lambda: propias)
    monkeypatch.setattr(practicas, "ruta_por_migrar", lambda: viejo)

    assert practicas.migrar_si_hace_falta() == 2
    escrito = propias.read_text(encoding="utf-8")
    assert "lo que este equipo ya había aprendido" in escrito
    assert "y esta otra regla también" in escrito
    assert not viejo.exists(), "el origen se borra: la mudanza ocurre una sola vez"
    assert "práctica que trae la versión nueva" in base.read_text(encoding="utf-8"), (
        "el archivo del paquete no se toca nunca"
    )


def test_la_mudanza_no_se_repite(monkeypatch, tmp_path) -> None:
    """Si ya existe el archivo propio, mudar otra vez lo pisaría."""
    from engine import practicas

    base = tmp_path / "PRACTICAS.md"
    base.write_text(
        f"# Base\n\n{practicas.MARCA_INICIO}\n\n- **ayer** — regla vieja\n\n"
        f"{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    propias = tmp_path / "practicas_aprendidas.md"
    propias.write_text(
        f"# Mias\n\n{practicas.MARCA_INICIO}\n\n- **hoy** — lo mío\n\n{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(practicas, "ruta_base", lambda: base)
    monkeypatch.setattr(practicas, "ruta", lambda: propias)

    assert practicas.migrar_si_hace_falta() == 0
    assert "lo mío" in propias.read_text(encoding="utf-8")


def test_sin_nada_que_mudar_no_crea_el_archivo(monkeypatch, tmp_path) -> None:
    from engine import practicas

    base = tmp_path / "PRACTICAS.md"
    base.write_text(
        f"# Base\n\n{practicas.MARCA_INICIO}\n\n{practicas.MARCA_FIN}\n", encoding="utf-8"
    )
    propias = tmp_path / "practicas_aprendidas.md"
    monkeypatch.setattr(practicas, "ruta_base", lambda: base)
    monkeypatch.setattr(practicas, "ruta", lambda: propias)

    assert practicas.migrar_si_hace_falta() == 0
    assert not propias.exists()


def test_en_desarrollo_no_se_muda_nada(monkeypatch, tmp_path) -> None:
    """Base y propia son el mismo archivo: mudar sería copiarlo sobre sí."""
    from engine import practicas

    unico = tmp_path / "PRACTICAS.md"
    unico.write_text(
        f"# X\n\n{practicas.MARCA_INICIO}\n\n- **hoy** — algo\n\n{practicas.MARCA_FIN}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(practicas, "ruta_base", lambda: unico)
    monkeypatch.setattr(practicas, "ruta", lambda: unico)

    assert practicas.migrar_si_hace_falta() == 0
