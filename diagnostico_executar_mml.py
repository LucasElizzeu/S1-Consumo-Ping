import yaml
from pathlib import Path
from playwright.sync_api import sync_playwright

from coleta_web import (
    BBU_USER,
    abrir_aba_mml,
    preencher_campo_command_f5,
    senha_do_site,
    tentar_login_generico,
    texto_de_todos_frames,
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
    abrir_aba_mml(page)
    preencher_campo_command_f5(page, "DSP S1INTERFACE;")

    for frame in page.frames:
        if "mml_exec" in frame.url:
            valor = frame.locator("#mmlcmdtext___input").first.input_value(timeout=3000)
            disabled_antes = frame.locator("#mmlexecbtn").first.get_attribute("disabled")
            frame.locator("#mmlexecbtn").first.evaluate("e => e.removeAttribute('disabled')")
            disabled_depois = frame.locator("#mmlexecbtn").first.get_attribute("disabled")
            frame.locator("#mmlexecbtn").first.click(timeout=3000, force=True)
            print(f"valor={valor!r} disabled_antes={disabled_antes!r} disabled_depois={disabled_depois!r}")
            break

    page.wait_for_timeout(8000)
    page.screenshot(path=r"C:\noc_tefe\prints\diagnostico_mml_executado.png", full_page=True)
    Path(r"C:\noc_tefe\bruto\diagnostico_mml_executado.txt").write_text(
        texto_de_todos_frames(page),
        encoding="utf-8",
        errors="ignore",
    )
    context.close()
    browser.close()
