import time
from pathlib import Path


BASE_DIR = Path(r"C:\noc_tefe")


def _remover_antigos(pasta: Path, dias: int, manter: set[str] | None = None):
    manter = manter or set()
    if not pasta.exists():
        return 0

    limite = time.time() - (dias * 24 * 60 * 60)
    removidos = 0

    for caminho in pasta.iterdir():
        if not caminho.is_file():
            continue
        if caminho.name in manter or caminho.name == ".gitkeep":
            continue

        try:
            if caminho.stat().st_mtime < limite:
                caminho.unlink()
                removidos += 1
        except Exception:
            pass

    return removidos


def limpar_arquivos_antigos():
    """Remove arquivos antigos sem tocar nas sessoes persistentes das BBUs."""
    total = 0
    total += _remover_antigos(BASE_DIR / "prints", dias=7)
    total += _remover_antigos(BASE_DIR / "bruto", dias=7)
    total += _remover_antigos(
        BASE_DIR / "saida",
        dias=7,
        manter={"boletim_tefe.png"},
    )
    total += _remover_antigos(
        BASE_DIR / "logs",
        dias=30,
        manter={"rotina_tefe.log"},
    )
    return total
