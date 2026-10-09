import json
from pathlib import Path


BASE_DIR = Path(r"C:\noc_tefe")
ARQUIVO_ESTADO = BASE_DIR / "alertas_silenciados.json"


def normalizar_site(texto: str) -> str:
    texto = " ".join(str(texto or "").strip().upper().replace("_", " ").split())
    if texto.startswith("BBU") and len(texto.split()) == 2:
        return f"BBU {texto.split()[1]}"
    if texto.startswith("AM TFE"):
        numero = texto.split()[-1].lstrip("0") or "0"
        return f"BBU {numero}"
    return texto


def carregar_silenciados() -> set[str]:
    if not ARQUIVO_ESTADO.exists():
        return set()

    try:
        dados = json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
        return {normalizar_site(item) for item in dados.get("silenciados", [])}
    except Exception:
        return set()


def salvar_silenciados(silenciados: set[str]):
    ARQUIVO_ESTADO.write_text(
        json.dumps({"silenciados": sorted(silenciados)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def silenciar_site(nome_site: str) -> str:
    site = normalizar_site(nome_site)
    silenciados = carregar_silenciados()
    silenciados.add(site)
    salvar_silenciados(silenciados)
    return site


def ativar_site(nome_site: str) -> str:
    site = normalizar_site(nome_site)
    silenciados = carregar_silenciados()
    silenciados.discard(site)
    salvar_silenciados(silenciados)
    return site


def alerta_silenciado(nome_site: str) -> bool:
    return normalizar_site(nome_site) in carregar_silenciados()


def listar_silenciados() -> list[str]:
    return sorted(carregar_silenciados())
