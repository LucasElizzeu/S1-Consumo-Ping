import os
import time
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


BASE_DIR = r"C:\noc_tefe"
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

GRAFANA_URL = os.getenv("GRAFANA_URL", "")
GRAFANA_USER = os.getenv("GRAFANA_USER", "")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "")

PAINEIS_TEFE = [139, 358, 359, 377, 378, 384, 385]


def formatar_bps(valor):
    if not isinstance(valor, (int, float)):
        return "-"

    valor = float(valor)
    if valor >= 1_000_000:
        return f"{valor / 1_000_000:.1f} Mb/s"
    if valor >= 1_000:
        return f"{valor / 1_000:.2f} kb/s"
    return f"{valor:.0f} b/s"


def _config_grafana():
    if not GRAFANA_URL or not GRAFANA_USER or not GRAFANA_PASSWORD:
        return None

    url = urlparse(GRAFANA_URL)
    partes = [parte for parte in url.path.split("/") if parte]
    if len(partes) < 2 or partes[0] != "d":
        return None

    return {
        "base": f"{url.scheme}://{url.netloc}",
        "uid": partes[1],
        "auth": (GRAFANA_USER, GRAFANA_PASSWORD),
    }


def _paineis_dashboard(config):
    resposta = requests.get(
        f"{config['base']}/api/dashboards/uid/{config['uid']}",
        auth=config["auth"],
        timeout=20,
    )
    resposta.raise_for_status()

    dashboard = resposta.json()["dashboard"]
    encontrados = {}
    pilha = list(dashboard.get("panels") or [])

    while pilha:
        painel = pilha.pop(0)
        pilha.extend(painel.get("panels") or [])
        painel_id = painel.get("id")
        if painel_id in PAINEIS_TEFE:
            encontrados[painel_id] = painel

    return encontrados


def _ultimo_valor_bps(config, target):
    agora = int(time.time() * 1000)
    inicio = agora - (60 * 60 * 1000)

    consulta = dict(target)
    consulta["intervalMs"] = 60_000
    consulta["maxDataPoints"] = 300

    resposta = requests.post(
        f"{config['base']}/api/ds/query",
        auth=config["auth"],
        json={"queries": [consulta], "from": str(inicio), "to": str(agora)},
        timeout=30,
    )
    resposta.raise_for_status()

    resultado = resposta.json().get("results", {}).get(consulta.get("refId", "A"), {})
    for frame in resultado.get("frames") or []:
        valores = ((frame.get("data") or {}).get("values") or [])
        if len(valores) < 2:
            continue

        for valor in reversed(valores[1]):
            if isinstance(valor, (int, float)):
                return float(valor)

    return None


def coletar_consumos_grafana(sites):
    consumos = {}
    config = _config_grafana()
    if not config:
        return consumos

    try:
        paineis = _paineis_dashboard(config)
    except Exception:
        return consumos

    for indice, site in enumerate(sites):
        if indice >= len(PAINEIS_TEFE):
            break

        painel = paineis.get(PAINEIS_TEFE[indice])
        targets = painel.get("targets") if painel else None
        if not targets:
            continue

        try:
            valor_bps = _ultimo_valor_bps(config, targets[0])
        except Exception:
            valor_bps = None

        if valor_bps is not None:
            consumos[site.get("nome", f"BBU {indice + 1}")] = {
                "consumo_bps": valor_bps,
                "consumo": formatar_bps(valor_bps),
            }

    return consumos
