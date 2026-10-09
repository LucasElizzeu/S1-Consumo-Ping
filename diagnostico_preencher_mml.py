import yaml
from playwright.sync_api import sync_playwright

from coleta_web import (
    BBU_USER,
    abrir_aba_mml,
    preencher_campo_command_f5,
    senha_do_site,
    tentar_login_generico,
)


with open(r"C:\noc_tefe\config_site_web.yaml", "r", encoding="utf-8") as arquivo:
    site = yaml.safe_load(arquivo)["sites"][0]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1366, "height": 768}, ignore_https_errors=True)
    page = context.new_page()
    page.goto(site["url"], wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    tentar_login_generico(page, BBU_USER, senha_do_site(site))
    page.wait_for_timeout(3000)
    abriu = abrir_aba_mml(page)
    preencheu = preencher_campo_command_f5(page, "DSP S1INTERFACE;")
    page.wait_for_timeout(2000)
    page.screenshot(path=r"C:\noc_tefe\prints\diagnostico_mml_preenchido.png", full_page=True)
    for frame in page.frames:
        if "mml_exec" in frame.url:
            valor = frame.locator("#mmlcmdtext___input").first.input_value(timeout=3000)
            disabled = frame.locator("#mmlexecbtn").first.get_attribute("disabled")
            print(f"abriu={abriu} preencheu={preencheu} valor={valor!r} exec_disabled={disabled!r}")
    context.close()
    browser.close()
