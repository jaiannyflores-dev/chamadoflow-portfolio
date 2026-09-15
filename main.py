"""Ponto de entrada compatível para executar o ChamadoFlow."""

import sys
from pathlib import Path


CAMINHO_SRC = Path(__file__).resolve().parent / "src"
if str(CAMINHO_SRC) not in sys.path:
    sys.path.insert(0, str(CAMINHO_SRC))

from chamadoflow.app import main


if __name__ == "__main__":
    main()
