import logging
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

import yaml

from coleta_web import coletar_site_web
from controle_alertas import alerta_silenciado
from grafana_consumo import coletar_consumos_grafana
from limpeza import limpar_arquivos_antigos
from planilha import gerar_imagem_boletim


BASE_DIR = r"C:\noc_tefe"
CONFIG = os.path.join(BASE_DIR, "config_site_web.yaml")
LOG_DIR = os.path.join(BASE_DIR, "logs")
MAX_COLETAS_PARALELAS = 2

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "rotina_tefe.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def carregar_config():
    with open(CONFIG, "r", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def extrair_host(site: dict) -> str:
    url = site.get("url") or site.get("ip") or ""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return parsed.hostname or url


def testar_ping(host: str, duracao_segundos: int = 15) -> dict:
    if not host:
        return {"host": host, "ok": False, "perda_pct": 100, "latencia_ms": None}

    pacotes = max(1, duracao_segundos // 3)
    comando = ["ping", "-n", str(pacotes), "-w", "3000", host]

    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="cp850",
            errors="ignore",
            timeout=duracao_segundos + 5,
        )
        saida = f"{proc.stdout}\n{proc.stderr}"
    except Exception as erro:
        return {
            "host": host,
            "ok": False,
            "perda_pct": 100,
            "latencia_ms": None,
            "erro": str(erro),
        }

    perda_pct = 100
    latencia_ms = None

    host_inacessivel = re.search(
        r"(?:host de destino inacess|destination host unreachable|destination net unreachable|general failure)",
        saida,
        flags=re.IGNORECASE,
    )
    perda = re.search(r"\((\d+)%\s*(?:de\s*)?(?:perda|loss)\)", saida, flags=re.IGNORECASE)
    if host_inacessivel:
        perda_pct = 100
    elif perda:
        perda_pct = int(perda.group(1))
    elif proc.returncode == 0:
        perda_pct = 0

    latencia = re.search(r"(?:M[eé]dia|Average)\s*=\s*(\d+)\s*ms", saida, flags=re.IGNORECASE)
    if latencia:
        latencia_ms = int(latencia.group(1))

    return {
        "host": host,
        "ok": perda_pct < 100,
        "perda_pct": perda_pct,
        "latencia_ms": latencia_ms,
    }


def resultado_sem_coleta(site: dict, status: str, erro: str, ping: dict | None = None) -> dict:
    return {
        "site": site.get("nome", "-"),
        "url": site.get("url", ""),
        "usuarios": None,
        "consumo": site.get("consumo"),
        "saida_s1interface": "",
        "saida_nrcell": "",
        "print_s1interface": "",
        "print_nrcell": "",
        "aaus": [],
        "nrcell_status": "",
        "erro": erro,
        "status": status,
        "ping": ping or {},
    }


def resumir_status(resultado: dict) -> str:
    erro = resultado.get("erro") or ""

    if resultado.get("status"):
        return resultado["status"]
    if isinstance(resultado.get("usuarios"), int):
        return "Normal"
    if "Login nao concluido" in erro:
        return "CAPTCHA/Login"
    if "Timeout no acesso web" in erro or "ERR_CONNECTION_TIMED_OUT" in erro:
        return "Web timeout"
    if erro:
        return "Coleta falhou"
    return "Sem dados"


def enviar_alerta(texto: str):
    logging.warning("ALERTA: %s", texto)


def enviar_alerta_site(site: dict, texto: str):
    if alerta_silenciado(site.get("nome", "")):
        logging.info("Alerta silenciado para %s: %s", site.get("nome"), texto)
        return
    enviar_alerta(texto)


def testar_pings_bbus(sites: list) -> list:
    resultados = [None] * len(sites)

    with ThreadPoolExecutor(max_workers=min(len(sites), 8) or 1) as executor:
        futuros = {
            executor.submit(testar_ping, extrair_host(site)): indice
            for indice, site in enumerate(sites)
        }

        for futuro in as_completed(futuros):
            indice = futuros[futuro]
            resultados[indice] = futuro.result()

    return resultados


def coletar_site_com_status(site: dict, ping: dict) -> dict:
    resultado = coletar_site_web(site)
    resultado["ping"] = ping
    resultado["status"] = resumir_status(resultado)
    return resultado


def main():
    logging.info("Iniciando rotina TEFE NOC")
    removidos = limpar_arquivos_antigos()
    if removidos:
        logging.info("Limpeza removeu %s arquivo(s) antigo(s)", removidos)

    config = carregar_config()
    cidade = config["cidade"]
    sites = config["sites"]
    consumos_grafana = coletar_consumos_grafana(sites)

    ping_local = testar_ping("8.8.8.8")
    if not ping_local["ok"]:
        enviar_alerta(
            "Alerta NOC TEFE: PC local sem resposta para 8.8.8.8 "
            f"({ping_local['perda_pct']}% de perda). A coleta das BBUs vai continuar."
        )

    pings_bbu = testar_pings_bbus(sites)
    resultados = [None] * len(sites)
    sites_para_coletar = []

    for indice, site in enumerate(sites):
        ping = pings_bbu[indice]
        if not ping["ok"]:
            resultados[indice] = resultado_sem_coleta(
                site,
                status="Sem ping",
                erro=f"BBU sem resposta ao ping ({ping['perda_pct']}% de perda)",
                ping=ping,
            )
            enviar_alerta_site(
                site,
                f"Alerta NOC TEFE: {site['nome']} sem ping para {ping['host']} "
                f"({ping['perda_pct']}% de perda). Coleta web pulada."
            )
            continue

        sites_para_coletar.append((indice, site, ping))

    with ThreadPoolExecutor(max_workers=MAX_COLETAS_PARALELAS) as executor:
        futuros = {
            executor.submit(coletar_site_com_status, site, ping): (indice, site)
            for indice, site, ping in sites_para_coletar
        }

        for futuro in as_completed(futuros):
            indice, site = futuros[futuro]
            try:
                resultado = futuro.result()
            except Exception as erro:
                resultado = resultado_sem_coleta(
                    site,
                    status="Coleta falhou",
                    erro=str(erro),
                    ping=pings_bbu[indice],
                )

            resultados[indice] = resultado

            if resultado.get("erro"):
                enviar_alerta_site(
                    site,
                    f"Alerta NOC TEFE: {site['nome']} - {resumir_status(resultado)}. "
                    f"Erro: {str(resultado['erro']).splitlines()[0]}"
                )

    resultados = [resultado for resultado in resultados if resultado is not None]
    for resultado in resultados:
        consumo = consumos_grafana.get(resultado.get("site"))
        if consumo:
            resultado.update(consumo)

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    caminho_imagem = gerar_imagem_boletim(
        cidade=cidade,
        data_hora=agora,
        resultados=resultados,
    )

    total_usuarios = sum(
        r["usuarios"] for r in resultados
        if isinstance(r.get("usuarios"), int)
    )

    legenda = (
        f"Boletim {cidade} - NOC\n"
        f"Horario: {agora}\n"
        f"Total usuarios: {total_usuarios}"
    )

if __name__ == "__main__":
    main()
