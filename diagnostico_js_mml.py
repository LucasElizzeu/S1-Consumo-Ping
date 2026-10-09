import requests
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
    abrir_aba_mml(page)
    preencher_campo_command_f5(page, "DSP S1INTERFACE")

    for frame in page.frames:
        if "mml_exec" not in frame.url:
            continue

        print("FRAME_URL=", frame.url)
        info = frame.evaluate(
            """() => {
                const b = document.querySelector('#mmlexecbtn');
                const a = document.querySelector('#mmlassistbtn');
                const c = document.querySelector('#mmlcmdtext___input');
                return {
                    execDisabled: b ? b.disabled : null,
                    execOnclick: b && b.onclick ? String(b.onclick) : null,
                    assistDisabled: a ? a.disabled : null,
                    assistOnclick: a && a.onclick ? String(a.onclick) : null,
                    cmdValue: c ? c.value : null,
                    windowKeys: Object.keys(window).filter(k => /mml|exec|cmd|assist/i.test(k)).slice(0, 80)
                };
            }"""
        )
        print(info)

        js_url = frame.url.rsplit("/", 1)[0] + "/../script/mml_exec.js"
        js_url = js_url.replace("/view/../", "/")
        try:
            r = requests.get(js_url, verify=False, timeout=15)
            print("JS_URL=", js_url, "status=", r.status_code, "len=", len(r.text))
            print(r.text[:4000])
        except Exception as erro:
            print("JS_FETCH_ERROR=", erro)
        break

    context.close()
    browser.close()
