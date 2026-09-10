"""Tests unitarios de app.services.fs (contención de rutas, listado, orden natural)."""
from pathlib import Path

from app.services import fs

BASE = "C:/Users/TI/Desktop/EntregaDocs"


def test_normalizar():
    assert fs.normalizar(r"C:\a\b") == "C:/a/b"
    assert fs.normalizar("C:/a/b/") == "C:/a/b"
    assert fs.normalizar("") == ""


def test_unir():
    assert fs.unir("C:/base", "archivo.pdf") == "C:/base/archivo.pdf"
    assert fs.unir("C:/base/", "/archivo.pdf") == "C:/base/archivo.pdf"


def test_confinar_subpath_ok():
    assert fs.confinar(BASE, BASE) == BASE
    assert fs.confinar(BASE, BASE + "/2026/AGOSTO") == BASE + "/2026/AGOSTO"
    assert fs.confinar(BASE, BASE + "/2026/AGOSTO/2337926.pdf") == BASE + "/2026/AGOSTO/2337926.pdf"


def test_confinar_rechaza_directorios_padres():
    assert fs.confinar(BASE, "C:/") is None
    assert fs.confinar(BASE, "C:/Users") is None
    assert fs.confinar(BASE, "C:/Users/TI/Desktop") is None


def test_confinar_rechaza_traversal():
    assert fs.confinar(BASE, BASE + "/..") is None
    assert fs.confinar(BASE, BASE + "/../..") is None
    assert fs.confinar(BASE, BASE + "/2026/../../FUERA") is None


def test_confinar_rechaza_otros_discos_y_vacios():
    assert fs.confinar(BASE, "D:/Otro") is None
    assert fs.confinar(BASE, "") is None
    assert fs.confinar(BASE, None) is None


def test_listar_dirs_y_pdfs(tmp_path: Path):
    (tmp_path / "carpeta").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / ".oculto").mkdir()
    assert fs.listar_dirs(str(tmp_path)) == ["carpeta"]
    assert fs.listar_pdfs(str(tmp_path)) == ["a.pdf"]


def test_natsort():
    assert fs._natsort(["10", "2", "1"]) == ["1", "2", "10"]
    assert fs._natsort(["a10", "a2", "a1"]) == ["a1", "a2", "a10"]
