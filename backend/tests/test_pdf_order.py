from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException

from app.services.pdf import extraer_paginas


def test_extraer_paginas_respeta_orden_personalizado(tmp_path: Path):
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    document = fitz.open()
    for number in (1, 2, 3):
        page = document.new_page()
        page.insert_text((72, 72), f"PAGINA-{number}")
    document.save(source)
    document.close()

    extraer_paginas(str(source), 1, 3, str(output), orden_paginas=[3, 1, 2])

    result = fitz.open(output)
    texts = [page.get_text().strip() for page in result]
    result.close()
    assert texts == ["PAGINA-3", "PAGINA-1", "PAGINA-2"]


def test_extraer_paginas_limita_cantidad(tmp_path: Path):
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    document = fitz.open()
    document.new_page()
    document.save(source)
    document.close()

    with pytest.raises(HTTPException) as error:
        extraer_paginas(str(source), 1, 501, str(output))

    assert error.value.status_code == 400
