"""Extracción de páginas de PDF con PyMuPDF."""
import fitz
from fastapi import HTTPException, status
from fastapi.responses import FileResponse


def _abrir(src: str) -> fitz.Document:
    try:
        doc = fitz.open(src)
    except Exception:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo abrir el PDF."
        )
    if doc.page_count == 0:
        doc.close()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El PDF no tiene páginas.")
    return doc


def extraer_paginas(src: str, inicio: int, fin: int, destino: str, rotacion: int = 0) -> int:
    """Extrae páginas [inicio..fin] (1-indexadas) a 'destino'. Devuelve nº de páginas."""
    doc = _abrir(src)
    total = doc.page_count
    if fin > total:
        doc.close()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"La página final ({fin}) supera el total ({total}).",
        )

    try:
        out = fitz.open()
        out.insert_pdf(doc, from_page=inicio - 1, to_page=fin - 1)
        if rotacion % 360 != 0:
            for p in out:
                p.set_rotation((p.rotation + rotacion) % 360)
        out.save(destino)
        count = out.page_count
        out.close()
        return count
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error al extraer páginas: {exc}"
        )
    finally:
        doc.close()


def pdf_response(path: str) -> FileResponse:
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Cache-Control": "private, no-store"},
    )