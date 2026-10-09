import yaml

from coleta_web import BBU_USER, senha_do_site, tentar_login_generico
from playwright.sync_api import sync_playwright
from pathlib import Path


with open(r"C:\noc_tefe\config_site_web.yaml", "r", encoding="utf-8") as arquivo:
    site = yaml.safe_load(arquivo)["sites"][0]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1366, "height": 768}, ignore_https_errors=True)
    page = context.new_page()
    page.goto(site["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    tentar_login_generico(page, BBU_USER, senha_do_site(site))
    page.wait_for_timeout(3000)

    for alvo in ["text=MML", "button:has-text('MML')", "input[value='MML']", "a:has-text('MML')"]:
        try:
            if page.locator(alvo).count() > 0:
                page.locator(alvo).first.click(timeout=5000)
                page.wait_for_timeout(4000)
                print(f"clicou={alvo}")
                break
        except Exception as erro:
            print(f"falha_click={alvo}: {type(erro).__name__}")

    print("url=", page.url)
    print("frames=", len(page.frames))
    for frame_index, frame in enumerate(page.frames):
        print(f"FRAME {frame_index}: {frame.url}")
        if "mml_exec" in frame.url:
            Path(r"C:\noc_tefe\bruto\mml_exec_frame.html").write_text(
                frame.content(),
                encoding="utf-8",
                errors="ignore",
            )
            print("  html salvo em C:\\noc_tefe\\bruto\\mml_exec_frame.html")
        if "welcome" in frame.url:
            Path(r"C:\noc_tefe\bruto\welcome_frame.html").write_text(
                frame.content(),
                encoding="utf-8",
                errors="ignore",
            )
            print("  html salvo em C:\\noc_tefe\\bruto\\welcome_frame.html")
        for seletor in ["input", "textarea", "button", "select", "[contenteditable='true']"]:
            try:
                itens = frame.locator(seletor)
                total = min(itens.count(), 20)
                print(f"  {seletor}: {itens.count()}")
                for indice in range(total):
                    item = itens.nth(indice)
                    print(
                        "   ",
                        indice,
                        "tag=", item.evaluate("e => e.tagName"),
                        "type=", item.get_attribute("type"),
                        "id=", item.get_attribute("id"),
                        "name=", item.get_attribute("name"),
                        "value=", repr(item.get_attribute("value")),
                    )
            except Exception as erro:
                print(f"  erro {seletor}: {type(erro).__name__}")

    context.close()
    browser.close()
