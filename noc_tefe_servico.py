import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from controle_alertas import alerta_silenciado
from coleta_web import (
    BBU_ACCESS_TIMEOUT_MS,
    BBU_USER,
    PRINTS_DIR,
    abrir_aba_mml,
    executar_comando_generico,
    extrair_aau_nrcell,
    extrair_usuarios_s1interface,
    fechar_dialogo_troca_senha_se_existir,
    limpar_erro_sensivel,
    nome_arquivo_seguro,
    pagina_parece_login,
    salvar_bruto,
    senha_do_site,
    tentar_login_generico,
)
from grafana_consumo import coletar_consumos_grafana
from limpeza import limpar_arquivos_antigos
from main import extrair_host, resultado_sem_coleta, resumir_status, testar_ping
from planilha import gerar_imagem_boletim


BASE_DIR = r"C:\noc_tefe"
CONFIG = os.path.join(BASE_DIR, "config_site_web.yaml")
SESSOES_DIR = Path(BASE_DIR) / "sessoes_bbu"
KEEPALIVE_SEGUNDOS = 8 * 60
COLETA_SEGUNDOS = 60 * 60
ENVIAR_TESTE_KEEPALIVE_TELEGRAM = True


def carregar_config():
    with open(CONFIG, "r", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def avisar(texto: str):
    print(texto)


def avisar_site(site: dict, texto: str):
    if alerta_silenciado(site.get("nome", "")):
        print(f"Alerta silenciado para {site.get('nome')}: {texto}")
        return
    avisar(texto)


class SessaoBBU:
    def __init__(self, playwright, site: dict):
        self.playwright = playwright
        self.site = site
        self.nome = site["nome"]
        self.host = extrair_host(site)
        self.context = None
        self.page = None
        self.erro = None
        self.ultimo_keepalive = None

    def abrir(self):
        if self.context:
            return

        pasta = SESSOES_DIR / nome_arquivo_seguro(self.nome)
        pasta.mkdir(parents=True, exist_ok=True)

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(pasta),
            headless=True,
            viewport={"width": 1366, "height": 768},
            ignore_https_errors=True,
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def fechar(self):
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        self.context = None
        self.page = None

    def garantir_login(self) -> bool:
        self.abrir()
        timeout_ms = int(self.site.get("access_timeout_ms") or BBU_ACCESS_TIMEOUT_MS)

        try:
            if not self.page.url or self.page.url == "about:blank":
                self.page.goto(self.site["url"], wait_until="domcontentloaded", timeout=timeout_ms)
                self.page.wait_for_timeout(2000)
            else:
                self.page.goto(self.site["url"], wait_until="domcontentloaded", timeout=timeout_ms)
                self.page.wait_for_timeout(1500)

            fechar_dialogo_troca_senha_se_existir(self.page)

            if pagina_parece_login(self.page):
                tentar_login_generico(self.page, BBU_USER, senha_do_site(self.site))
                self.page.wait_for_timeout(2500)
                fechar_dialogo_troca_senha_se_existir(self.page)

            if pagina_parece_login(self.page):
                self.erro = "Login/CAPTCHA pendente. Sessao nao mantida."
                return False

            self.erro = None
            return True
        except Exception as erro:
            self.erro = limpar_erro_sensivel(erro)
            return False

    def keepalive(self) -> bool:
        try:
            if not self.garantir_login():
                return False

            # Uma interacao leve na propria interface renova o idle timeout sem executar comando.
            abrir_aba_mml(self.page)
            self.ultimo_keepalive = datetime.now()
            return True
        except Exception as erro:
            self.erro = limpar_erro_sensivel(erro)
            return False

    def coletar(self, ping: dict) -> dict:
        resultado = {
            "site": self.nome,
            "url": self.site.get("url", ""),
            "usuarios": None,
            "consumo": self.site.get("consumo"),
            "saida_s1interface": "",
            "saida_nrcell": "",
            "print_s1interface": "",
            "print_nrcell": "",
            "aaus": [],
            "nrcell_status": "",
            "erro": None,
            "ping": ping,
        }

        if not self.garantir_login():
            resultado["erro"] = self.erro or "Login/CAPTCHA pendente"
            resultado["status"] = resumir_status(resultado)
            return resultado

        nome_seguro = nome_arquivo_seguro(self.nome)

        try:
            if self.site.get("s1interface"):
                texto_s1 = executar_comando_generico(self.page, "DSP S1INTERFACE;")
                resultado["saida_s1interface"] = texto_s1
                resultado["usuarios"] = extrair_usuarios_s1interface(texto_s1)
                salvar_bruto(self.nome, "s1interface", texto_s1)

                PRINTS_DIR.mkdir(parents=True, exist_ok=True)
                caminho_print = PRINTS_DIR / f"{nome_seguro}_s1interface.png"
                self.page.screenshot(path=str(caminho_print), full_page=True)
                resultado["print_s1interface"] = str(caminho_print)

                if resultado["usuarios"] is None:
                    resultado["erro"] = "DSP S1INTERFACE executado sem valor de usuarios reconhecido."

            if self.site.get("nrcell"):
                texto_nrcell = executar_comando_generico(self.page, "DSP NRCELLUENUMBER;")
                resultado["saida_nrcell"] = texto_nrcell
                resultado["aaus"] = extrair_aau_nrcell(texto_nrcell)
                resultado["nrcell_status"] = "NRCELL coletado"
                salvar_bruto(self.nome, "nrcell", texto_nrcell)

                PRINTS_DIR.mkdir(parents=True, exist_ok=True)
                caminho_print = PRINTS_DIR / f"{nome_seguro}_nrcell.png"
                self.page.screenshot(path=str(caminho_print), full_page=True)
                resultado["print_nrcell"] = str(caminho_print)

        except PlaywrightTimeoutError as erro:
            resultado["erro"] = f"Timeout no acesso web: {limpar_erro_sensivel(erro)}"
        except Exception as erro:
            resultado["erro"] = limpar_erro_sensivel(erro)

        resultado["status"] = resumir_status(resultado)
        return resultado


def proxima_coleta():
    agora = datetime.now()
    proxima = agora.replace(minute=55, second=0, microsecond=0)
    if agora >= proxima:
        proxima = proxima + timedelta(hours=1)
    return proxima


def executar_rodada(config: dict, sessoes: list[SessaoBBU]):
    cidade = config["cidade"]
    sites = config["sites"]
    consumos_grafana = coletar_consumos_grafana(sites)

    resultados = []
    for sessao in sessoes:
        ping = testar_ping(sessao.host)
        if not ping["ok"]:
            resultado = resultado_sem_coleta(
                sessao.site,
                status="Sem ping",
                erro=f"BBU sem resposta ao ping ({ping['perda_pct']}% de perda)",
                ping=ping,
            )
            avisar_site(sessao.site, f"Alerta NOC TEFE: {sessao.nome} sem ping para {ping['host']}. Coleta pulada.")
        else:
            resultado = sessao.coletar(ping)
            if resultado.get("erro"):
                avisar_site(
                    sessao.site,
                    f"Alerta NOC TEFE: {sessao.nome} - {resumir_status(resultado)}. "
                    f"Erro: {str(resultado['erro']).splitlines()[0]}"
                )

        consumo = consumos_grafana.get(resultado.get("site"))
        if consumo:
            resultado.update(consumo)
        resultados.append(resultado)

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    imagem = gerar_imagem_boletim(cidade, agora, resultados)
    total_usuarios = sum(r["usuarios"] for r in resultados if isinstance(r.get("usuarios"), int))

    print(f"Rodada enviada: {agora} | usuarios={total_usuarios}")


def enviar_teste_keepalive(sessoes: list[SessaoBBU]):
    linhas = [f"Teste keepalive NOC TEFE - {datetime.now():%d/%m/%Y %H:%M}"]

    for sessao in sessoes:
        ping = testar_ping(sessao.host, duracao_segundos=6)
        if not ping["ok"]:
            linhas.append(f"{sessao.nome}: sem ping")
            continue

        if not sessao.garantir_login():
            linhas.append(f"{sessao.nome}: login/CAPTCHA pendente")
            continue

        try:
            texto_s1 = executar_comando_generico(sessao.page, "DSP S1INTERFACE;")
            usuarios = extrair_usuarios_s1interface(texto_s1)
            if isinstance(usuarios, int):
                linhas.append(f"{sessao.nome}: {usuarios} usuarios | ping {ping.get('latencia_ms', '-')}ms")
            else:
                linhas.append(f"{sessao.nome}: sem valor de usuarios | ping {ping.get('latencia_ms', '-')}ms")
        except Exception as erro:
            linhas.append(f"{sessao.nome}: falha no teste - {limpar_erro_sensivel(erro).splitlines()[0]}")

    mensagem = "\n".join(linhas)
    print(mensagem)


def main():
    config = carregar_config()
    sites = config["sites"]
    SESSOES_DIR.mkdir(parents=True, exist_ok=True)
    removidos = limpar_arquivos_antigos()

    print("Servico NOC TEFE iniciado.")
    print("Keepalive a cada 8 minutos. Coleta no inicio de cada hora.")
    if removidos:
        print(f"Limpeza removeu {removidos} arquivo(s) antigo(s).")

    with sync_playwright() as playwright:
        sessoes = [SessaoBBU(playwright, site) for site in sites]

        for sessao in sessoes:
            ping = testar_ping(sessao.host, duracao_segundos=6)
            if not ping["ok"]:
                print(f"{sessao.nome}: sem ping inicial, sessao nao aberta agora.")
                continue

            if sessao.keepalive():
                print(f"{sessao.nome}: sessao pronta.")
            else:
                avisar_site(sessao.site, f"Alerta NOC TEFE: {sessao.nome} nao manteve sessao. {sessao.erro}")

        proxima = proxima_coleta()
        proximo_teste_keepalive = datetime.now() + timedelta(seconds=KEEPALIVE_SEGUNDOS)
        print(f"Proxima coleta: {proxima:%d/%m/%Y %H:%M}")

        try:
            while True:
                agora = datetime.now()

                if agora >= proxima:
                    executar_rodada(config, sessoes)
                    proxima = proxima + timedelta(seconds=COLETA_SEGUNDOS)
                    print(f"Proxima coleta: {proxima:%d/%m/%Y %H:%M}")

                if ENVIAR_TESTE_KEEPALIVE_TELEGRAM and agora >= proximo_teste_keepalive:
                    enviar_teste_keepalive(sessoes)
                    proximo_teste_keepalive = datetime.now() + timedelta(seconds=KEEPALIVE_SEGUNDOS)

                for sessao in sessoes:
                    if (
                        sessao.ultimo_keepalive is None
                        or (agora - sessao.ultimo_keepalive).total_seconds() >= KEEPALIVE_SEGUNDOS
                    ):
                        ping = testar_ping(sessao.host, duracao_segundos=6)
                        if ping["ok"]:
                            ok = sessao.keepalive()
                            print(f"{datetime.now():%H:%M:%S} keepalive {sessao.nome}: {'OK' if ok else 'falhou'}")

                time.sleep(30)
        except KeyboardInterrupt:
            print("Encerrando servico...")
        finally:
            for sessao in sessoes:
                sessao.fechar()


if __name__ == "__main__":
    main()
