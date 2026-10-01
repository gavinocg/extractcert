"""Extracción de páginas de PDF con PyMuPDF."""
import os

import fitz
from fastapi import HTTPException, status
from fastapi.responses import FileResponse


MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", str(250 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "5000"))
MAX_EXTRACTION_PAGES = int(os.getenv("MAX_EXTRACTION_PAGES", "500"))


def _abrir(src: str) -> fitz.Document:
    if os.path.getsize(src) > MAX_PDF_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "El PDF supera el tamaño permitido.")
    try:
        doc = fitz.open(src)
    except Exception:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No se pudo abrir el PDF."
        )
    if doc.page_count == 0:
        doc.close()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El PDF no tiene páginas.")
    if doc.page_count > MAX_PDF_PAGES:
        doc.close()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El PDF supera el número de páginas permitido.")
    return doc


def extraer_paginas(src: str, inicio: int, fin: int, destino: str, rotacion: int = 0, orden_paginas: list[int] | None = None) -> int:
    """Extrae páginas [inicio..fin] (1-indexadas) a 'destino'. Devuelve nº de páginas."""
    if fin - inicio + 1 > MAX_EXTRACTION_PAGES or len(orden_paginas or []) > MAX_EXTRACTION_PAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La extracción supera el límite de páginas.")
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
        natural = list(range(inicio, fin + 1))
        ordered = [page for page in (orden_paginas or []) if inicio <= page <= fin]
        ordered = list(dict.fromkeys(ordered))
        ordered.extend(page for page in natural if page not in ordered)
        for page in ordered:
            out.insert_pdf(doc, from_page=page - 1, to_page=page - 1)
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
