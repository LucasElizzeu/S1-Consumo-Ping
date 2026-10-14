import os
import re
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE_DIR = r"C:\noc_tefe"
load_dotenv(os.path.join(BASE_DIR, ".env"))

BBU_USER = os.getenv("BBU_USER")
BBU_PASSWORD_DEFAULT = os.getenv("BBU_PASSWORD_DEFAULT") or os.getenv("BBU_PASSWORD_1_A_6")
BBU_PASSWORD_2 = os.getenv("BBU_PASSWORD_2")
BBU_PASSWORD_3 = os.getenv("BBU_PASSWORD_3")
BBU_PASSWORD_7 = os.getenv("BBU_PASSWORD_7")
BBU_MANUAL_LOGIN = os.getenv("BBU_MANUAL_LOGIN", "")
BBU_ACCESS_TIMEOUT_MS = int(os.getenv("BBU_ACCESS_TIMEOUT_MS", "20000"))

BRUTO_DIR = Path(BASE_DIR) / "bruto"
PRINTS_DIR = Path(BASE_DIR) / "prints"


def nome_arquivo_seguro(nome: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", nome.strip())


def senha_do_site(site: dict) -> str:
    grupo = str(site.get("credential_group", "padrao")).strip().lower()
    nome = str(site.get("nome", "")).strip().upper()

    if grupo in ("bbu2", "grupo_2") or nome == "BBU 2":
        return BBU_PASSWORD_2 or BBU_PASSWORD_DEFAULT or ""
    if grupo in ("bbu3", "grupo_3") or nome == "BBU 3":
        return BBU_PASSWORD_3 or ""
    if grupo == "grupo_7":
        return BBU_PASSWORD_7 or BBU_PASSWORD_DEFAULT or ""
    return BBU_PASSWORD_DEFAULT or ""


def valor_placeholder(valor: str) -> bool:
    return not valor or valor.strip().upper().startswith("COLE_AQUI")


def valor_verdadeiro(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().lower() in ("1", "true", "yes", "sim", "s")


def valor_auto(valor) -> bool:
    return str(valor or "").strip().lower() in ("auto", "captcha", "cap")


def limpar_erro_sensivel(erro: Exception) -> str:
    texto = str(erro)
    for segredo in (BBU_PASSWORD_DEFAULT, BBU_PASSWORD_2, BBU_PASSWORD_3, BBU_PASSWORD_7, BBU_USER):
        if segredo:
            texto = texto.replace(segredo, "***")
    return texto


def extrair_usuarios_s1interface(texto: str):
    """Extrai usuarios somente da coluna S1 Interface User Number."""
    if not texto:
        return None

    usuarios_tabela = []
    indice_coluna_usuario = None

    for linha in texto.splitlines():
        linha_normalizada = linha.replace("\xa0", " ")
        linha_limpa = " ".join(linha_normalizada.split())
        linha_lower = linha_normalizada.lower()

        if "s1 interface user number" in linha_lower:
            colunas = re.split(r"\s{2,}", linha_normalizada.strip())
            colunas_lower = [" ".join(col.lower().split()) for col in colunas]
            try:
                indice_coluna_usuario = colunas_lower.index("s1 interface user number")
            except ValueError:
                return None
            continue

        if indice_coluna_usuario is not None and (
            "number of results" in linha_lower
            or linha_limpa.startswith("---")
            or linha_limpa.upper() == "END"
        ):
            break

        if indice_coluna_usuario is not None:
            colunas = re.split(r"\s{2,}", linha_normalizada.strip())
            if len(colunas) > indice_coluna_usuario:
                valor = colunas[indice_coluna_usuario].strip()
                if valor.isdigit():
                    usuarios_tabela.append(int(valor))

    if usuarios_tabela:
        return sum(usuarios_tabela)

    return None


def extrair_aau_nrcell(texto: str):
    """Extrai AAUs/setores e quantidade UE/RRC da saida de DSP NRCELLUENUMBER."""
    if not texto:
        return []

    aaus = []
    vistos = set()
    lendo_tabela_cell = False

    for linha in texto.splitlines():
        linha_normalizada = linha.replace("\xa0", " ")
        linha_limpa = " ".join(linha_normalizada.split())
        if not linha_limpa:
            continue

        if "cell name" in linha_limpa.lower() and "total rrc number" in linha_limpa.lower():
            lendo_tabela_cell = True
            continue

        if not lendo_tabela_cell:
            continue

        if "number of results" in linha_limpa.lower() or linha_limpa.startswith("---"):
            break

        partes = linha_limpa.split()
        if len(partes) < 7 or not partes[0].isdigit():
            continue

        cell_name = partes[1].upper().replace("-", "_")
        numeros = [int(valor) for valor in partes[2:] if valor.isdigit()]
        if len(numeros) < 5:
            continue

        usuarios = numeros[4]
        achou_setor = re.search(r"(N\d+_S\d+|N\d+[-_]S\d+|S\d+)$", cell_name)
        aau = achou_setor.group(1).replace("-", "_") if achou_setor else cell_name
        chave = (aau, usuarios)
        if chave not in vistos:
            aaus.append({"aau": aau, "usuarios": usuarios})
            vistos.add(chave)

    return aaus


def salvar_bruto(nome_site: str, tipo: str, texto: str):
    BRUTO_DIR.mkdir(parents=True, exist_ok=True)
    nome = nome_arquivo_seguro(nome_site)
    caminho = BRUTO_DIR / f"{nome}_{tipo}.txt"

    with open(caminho, "w", encoding="utf-8", errors="ignore") as f:
        f.write(texto or "")

    return str(caminho)


def confirmar_aviso_se_existir(page):
    seletores_sim = [
        "button:has-text('Yes')",
        "input[value='Yes']",
        "text=Yes",
        "button:has-text('Sim')",
        "input[value='Sim']",
        "text=Sim",
    ]

    for seletor in seletores_sim:
        try:
            if page.locator(seletor).count() > 0:
                page.locator(seletor).first.click(timeout=3000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass

    return False


def fechar_dialogo_troca_senha_se_existir(page):
    """Fecha o aviso de troca/expiracao de senha que aparece apos o login."""
    alvos = [page, *page.frames]

    for alvo in alvos:
        try:
            texto = alvo.inner_text("body", timeout=1000).lower()
        except Exception:
            texto = ""

        if (
            "change password" not in texto
            and "password will expire" not in texto
            and "your password will expire" not in texto
        ):
            continue

        seletores_cancelar = [
            "button:has-text('Cancel')",
            "input[value='Cancel']",
            "text=Cancel",
            "button:has-text('Cancelar')",
            "input[value='Cancelar']",
            "text=Cancelar",
        ]

        for seletor in seletores_cancelar:
            try:
                if alvo.locator(seletor).count() > 0:
                    alvo.locator(seletor).first.click(timeout=2500, force=True)
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass

        seletores_fechar = [
            "[title='Close']",
            "[aria-label='Close']",
            ".x-tool-close",
            ".x-tool:has-text('x')",
            "img.x-tool-close",
        ]

        for seletor in seletores_fechar:
            try:
                if alvo.locator(seletor).count() > 0:
                    alvo.locator(seletor).first.click(timeout=2500, force=True)
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass

        try:
            fechou = alvo.evaluate(
                """
                () => {
                    const candidatos = Array.from(document.querySelectorAll('*'));
                    const visivel = (el) => {
                        const st = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
                    };
                    const botoes = candidatos.filter((el) => {
                        const txt = (el.innerText || el.value || el.title || '').trim().toLowerCase();
                        const cls = (el.className || '').toString().toLowerCase();
                        return visivel(el) && (txt === 'cancel' || txt === 'cancelar' || cls.includes('x-tool-close'));
                    });
                    if (!botoes.length) return false;
                    botoes[0].click();
                    return true;
                }
                """
            )
            if fechou:
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass

    return False


def pagina_parece_login(page):
    try:
        campos_senha = page.locator("input[type='password']")
        for indice in range(campos_senha.count()):
            if campos_senha.nth(indice).is_visible(timeout=1000):
                return True
    except Exception:
        pass

    try:
        texto = page.inner_text("body", timeout=5000).lower()
    except Exception:
        return False

    marcadores = [
        "user name",
        "password",
        "verification code",
        "login",
        "local maintenance terminal",
    ]
    return sum(1 for item in marcadores if item in texto) >= 3


def aguardar_login_manual(page, nome_site: str):
    print("")
    print(f"Login manual necessario para {nome_site}.")
    print("No navegador que abriu, faca o login da BBU, informe o Verification code/CAPTCHA e aguarde carregar o terminal.")
    input("Quando o terminal estiver aberto, volte aqui e pressione ENTER para continuar a coleta...")
    page.wait_for_timeout(1500)


def tentar_login_generico(page, usuario: str, senha: str):
    confirmar_aviso_se_existir(page)
    fechar_dialogo_troca_senha_se_existir(page)

    seletores_usuario = [
        "input[name='username']",
        "input[name='user']",
        "input[name='login']",
        "input[id='username']",
        "input[id='user']",
        "input[id='login']",
        "input[type='text']",
    ]
    seletores_senha = [
        "input[name='password']",
        "input[name='senha']",
        "input[id='password']",
        "input[id='senha']",
        "input[type='password']",
    ]

    campo_usuario = next((s for s in seletores_usuario if page.locator(s).count() > 0), None)
    campo_senha = next((s for s in seletores_senha if page.locator(s).count() > 0), None)

    if campo_usuario:
        page.fill(campo_usuario, usuario, timeout=5000)
    if campo_senha:
        try:
            page.fill(campo_senha, senha, timeout=5000)
        except Exception:
            campo = page.locator(campo_senha).first
            campo.evaluate("e => { e.removeAttribute('readonly'); e.readOnly = false; }")
            campo.fill(senha, timeout=5000)

    # A BBU exige o campo "User type" (Local/EMS); se o select ficar vazio o login nao conclui.
    try:
        selects = page.locator("select")
        for indice in range(selects.count()):
            sel = selects.nth(indice)
            if not sel.is_visible(timeout=1000):
                continue

            if sel.input_value():
                continue

            opcoes = sel.locator("option")
            for op in range(opcoes.count()):
                valor = opcoes.nth(op).get_attribute("value")
                if valor:
                    sel.select_option(valor)
                    page.wait_for_timeout(500)
                    break
    except Exception:
        pass

    seletores_botao = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Log in')",
        "button:has-text('Entrar')",
        "input[value='Login']",
        "input[value='Entrar']",
    ]

    for seletor in seletores_botao:
        if page.locator(seletor).count() > 0:
            page.locator(seletor).first.click(timeout=5000, force=True)
            page.wait_for_timeout(5000)
            confirmar_aviso_se_existir(page)
            fechar_dialogo_troca_senha_se_existir(page)
            if not pagina_parece_login(page):
                return

    seletores_botao_generico = [
        "input[type='button']",
        "input[type='image']",
        "button",
    ]

    for seletor in seletores_botao_generico:
        try:
            botoes = page.locator(seletor)
            for indice in range(botoes.count()):
                botao = botoes.nth(indice)
                if botao.is_visible(timeout=1000) and botao.is_enabled(timeout=1000):
                    botao.click(timeout=5000)
                    page.wait_for_timeout(5000)
                    confirmar_aviso_se_existir(page)
                    fechar_dialogo_troca_senha_se_existir(page)
                    if not pagina_parece_login(page):
                        return
        except Exception:
            pass

    page.keyboard.press("Enter")
    page.wait_for_timeout(5000)
    confirmar_aviso_se_existir(page)
    fechar_dialogo_troca_senha_se_existir(page)


def campo_command_f5_disponivel(page):
    for frame in page.frames:
        if "mml_exec" not in frame.url:
            continue

        try:
            campo = frame.locator("#mmlcmdtext___input").first
            if campo.count() > 0 and campo.is_visible(timeout=1000):
                return True
        except Exception:
            pass

    return False


def abrir_aba_mml(page):
    seletores_mml = [
        "button:has-text('MML')",
        "input[value='MML']",
        "a:has-text('MML')",
        "text=MML",
    ]

    for _ in range(5):
        if campo_command_f5_disponivel(page):
            return True

        for seletor in seletores_mml:
            try:
                if page.locator(seletor).count() > 0:
                    page.locator(seletor).first.click(timeout=5000)
                    page.wait_for_timeout(3000)
                    if campo_command_f5_disponivel(page):
                        return True
            except Exception:
                pass

        try:
            page.mouse.click(460, 50)
            page.wait_for_timeout(5000)
            if campo_command_f5_disponivel(page):
                return True
        except Exception:
            pass

        for frame in page.frames:
            try:
                if "welcome" not in frame.url:
                    continue

                icones = frame.locator(".icon")
                if icones.count() > 0:
                    icones.first.click(timeout=5000, force=True)
                    page.wait_for_timeout(5000)
                    if campo_command_f5_disponivel(page):
                        return True
            except Exception:
                pass

    return False


def fechar_dialogo_info(page):
    seletores_ok = [
        "button:has-text('OK')",
        "input[value='OK']",
        "text=OK",
    ]

    for seletor in seletores_ok:
        try:
            if page.locator(seletor).count() > 0:
                page.locator(seletor).first.click(timeout=2000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            pass

    return False


def preencher_campo_command_f5(page, comando: str):
    comando = comando.rstrip(" ;")

    for frame in page.frames:
        if "mml_exec" not in frame.url:
            continue

        try:
            campo = frame.locator("#mmlcmdtext___input")
            if campo.count() > 0 and campo.first.is_visible(timeout=1000):
                campo.first.click(timeout=5000)
                campo.first.press("Control+A", timeout=3000)
                campo.first.press("Backspace", timeout=3000)
                campo.first.type(comando, delay=20, timeout=10000)
                try:
                    campo.first.evaluate(
                        """(elemento, valor) => {
                            elemento.value = valor;
                            elemento.dispatchEvent(new Event('input', {bubbles: true}));
                            elemento.dispatchEvent(new Event('change', {bubbles: true}));
                        }""",
                        comando,
                    )
                except Exception:
                    pass
                return True
        except Exception:
            pass

    return False


def clicar_assist(page):
    seletores_assist = [
        "button:has-text('Assist')",
        "input[value='Assist']",
        "text=Assist",
    ]

    for seletor in seletores_assist:
        try:
            if page.locator(seletor).count() > 0:
                page.locator(seletor).first.click(timeout=5000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            pass

    for frame in page.frames:
        for seletor in seletores_assist:
            try:
                if frame.locator(seletor).count() > 0:
                    frame.locator(seletor).first.click(timeout=5000)
                    page.wait_for_timeout(1000)
                    return True
            except Exception:
                pass

    return False


def assist_gerou_interface(page):
    for frame in page.frames:
        try:
            texto = frame.inner_text("body", timeout=1000)
        except Exception:
            continue

        if "S1 INTERFACE" in texto.upper() or "S1INTERFACE" in texto.upper():
            return True

    return False


def aguardar_assist_interface(page, timeout_ms: int = 10000):
    tentativas = max(1, timeout_ms // 500)

    for _ in range(tentativas):
        if assist_gerou_interface(page):
            return True
        page.wait_for_timeout(500)

    return False


def aguardar_exec_habilitado(page, timeout_ms: int = 10000):
    tentativas = max(1, timeout_ms // 500)

    for _ in range(tentativas):
        for frame in page.frames:
            for seletor in ("button:has-text('Exec')", "input[value='Exec']", "text=Exec"):
                try:
                    botao = frame.locator(seletor).first
                    if botao.count() > 0 and botao.is_enabled(timeout=500):
                        return True
                except Exception:
                    pass
        page.wait_for_timeout(500)

    return False


def preencher_em_qualquer_frame(page, seletores: list, valor: str):
    for frame in page.frames:
        for seletor in seletores:
            try:
                campo = frame.locator(seletor)
                if campo.count() > 0 and campo.first.is_visible(timeout=500):
                    campo.first.click(timeout=3000)
                    campo.first.press("Control+A", timeout=2000)
                    campo.first.press("Backspace", timeout=2000)
                    campo.first.type(valor, delay=20, timeout=5000)
                    return True
            except Exception:
                pass

    return False


def clicar_execucao(page):
    seletores_exec = [
        "button:has-text('Exec')",
        "input[value='Exec']",
        "text=Exec",
    ]

    for _ in range(10):
        for seletor in seletores_exec:
            try:
                if page.locator(seletor).count() > 0:
                    botao = page.locator(seletor).first
                    if botao.is_visible(timeout=1000) and botao.is_enabled(timeout=1000):
                        botao.click(timeout=5000, force=True)
                        page.wait_for_timeout(5000)
                        return True
            except Exception:
                pass

        for frame in page.frames:
            for seletor in seletores_exec:
                try:
                    if frame.locator(seletor).count() > 0:
                        botao = frame.locator(seletor).first
                        if botao.is_visible(timeout=1000) and botao.is_enabled(timeout=1000):
                            botao.click(timeout=5000, force=True)
                            page.wait_for_timeout(5000)
                            return True
                except Exception:
                    pass

        page.wait_for_timeout(1000)

    return False


def texto_resultado_mml(page):
    pedacos = []

    for frame in page.frames:
        try:
            texto = frame.inner_text("body", timeout=1000)
            if texto:
                pedacos.append(texto)
        except Exception:
            pass

    return "\n".join(pedacos)


def limpar_resultado_mml(page):
    for frame in page.frames:
        for seletor in ("button:has-text('Clear')", "input[value='Clear']"):
            try:
                if frame.locator(seletor).count() > 0:
                    frame.locator(seletor).first.click(timeout=2000)
                    page.wait_for_timeout(800)
                    return
            except Exception:
                pass


def aguardar_resultado_comando(page, comando: str, timeout_ms: int = 30000):
    tentativas = max(1, timeout_ms // 1000)
    alvo = comando.split()[0].upper() if comando else ""

    for _ in range(tentativas):
        texto = texto_resultado_mml(page)
        if "number of results" in texto.lower() or "END" in texto:
            return texto
        if alvo and alvo in texto.upper() and len(texto) > 200:
            return texto
        page.wait_for_timeout(1000)

    return texto_resultado_mml(page)


def executar_comando_generico(page, comando: str):
    if not abrir_aba_mml(page):
        raise RuntimeError("Nao foi possivel abrir a aba MML.")

    limpar_resultado_mml(page)

    if not preencher_campo_command_f5(page, comando):
        raise RuntimeError("Nao foi possivel preencher o campo de comando MML.")

    page.wait_for_timeout(500)
    clicar_assist(page)

    if not aguardar_assist_interface(page, timeout_ms=10000):
        pass

    aguardar_exec_habilitado(page, timeout_ms=10000)

    if not clicar_execucao(page):
        raise RuntimeError("Nao foi possivel executar o comando MML.")

    texto = aguardar_resultado_comando(page, comando, timeout_ms=30000)
    fechar_dialogo_info(page)
    return texto


def resultado_base(site: dict):
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
        "erro": None,
    }


def encerrar_sessao_bbu(page):
    for frame in page.frames:
        for seletor in ("button:has-text('Logout')", "a:has-text('Logout')", "text=Logout"):
            try:
                if frame.locator(seletor).count() > 0:
                    frame.locator(seletor).first.click(timeout=3000, force=True)
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass

    return False


def executar_coleta_com_browser(p, site: dict, resultado: dict, login_manual: bool):
    nome_site = site["nome"]
    url = site["url"]
    nome_seguro = nome_arquivo_seguro(nome_site)
    timeout_ms = int(site.get("access_timeout_ms") or BBU_ACCESS_TIMEOUT_MS)

    browser = p.chromium.launch(headless=not login_manual)
    context = browser.new_context(viewport={"width": 1366, "height": 768}, ignore_https_errors=True)
    page = context.new_page()

    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(2000)
    fechar_dialogo_troca_senha_se_existir(page)
    try:
        tentar_login_generico(page, BBU_USER, senha_do_site(site))
    except Exception:
        if not login_manual:
            raise

    if login_manual and pagina_parece_login(page):
        aguardar_login_manual(page, nome_site)

    if pagina_parece_login(page):
        resultado["erro"] = "Login nao concluido. A pagina da BBU exige codigo de verificacao/CAPTCHA ou seletores especificos."
        PRINTS_DIR.mkdir(parents=True, exist_ok=True)
        caminho_print = PRINTS_DIR / f"{nome_seguro}_login.png"
        page.screenshot(path=str(caminho_print), full_page=True)
        resultado["print_s1interface"] = str(caminho_print)
        encerrar_sessao_bbu(page)
        context.close()
        browser.close()
        return resultado, True

    if site.get("s1interface"):
        texto_s1 = executar_comando_generico(page, "DSP S1INTERFACE;")
        resultado["saida_s1interface"] = texto_s1
        resultado["usuarios"] = extrair_usuarios_s1interface(texto_s1)
        salvar_bruto(nome_site, "s1interface", texto_s1)

        PRINTS_DIR.mkdir(parents=True, exist_ok=True)
        caminho_print = PRINTS_DIR / f"{nome_seguro}_s1interface.png"
        page.screenshot(path=str(caminho_print), full_page=True)
        resultado["print_s1interface"] = str(caminho_print)

        if resultado["usuarios"] is None:
            resultado["erro"] = "DSP S1INTERFACE executado sem valor de usuarios reconhecido. Verifique bruto/print da BBU."

    if site.get("nrcell"):
        texto_nrcell = executar_comando_generico(page, "DSP NRCELLUENUMBER;")
        resultado["saida_nrcell"] = texto_nrcell
        resultado["aaus"] = extrair_aau_nrcell(texto_nrcell)
        resultado["nrcell_status"] = "NRCELL coletado"
        salvar_bruto(nome_site, "nrcell", texto_nrcell)

        PRINTS_DIR.mkdir(parents=True, exist_ok=True)
        caminho_print = PRINTS_DIR / f"{nome_seguro}_nrcell.png"
        page.screenshot(path=str(caminho_print), full_page=True)
        resultado["print_nrcell"] = str(caminho_print)

    encerrar_sessao_bbu(page)
    context.close()
    browser.close()
    return resultado, False


def coletar_site_web(site: dict):
    resultado = resultado_base(site)

    if valor_placeholder(BBU_USER):
        resultado["erro"] = "BBU_USER nao configurado corretamente no .env"
        return resultado

    senha = senha_do_site(site)
    if valor_placeholder(senha):
        resultado["erro"] = "Senha da BBU nao configurada corretamente no .env"
        return resultado

    login_manual_forcado = valor_verdadeiro(site.get("manual_login")) or valor_verdadeiro(BBU_MANUAL_LOGIN)
    login_auto = valor_auto(site.get("manual_login")) or valor_auto(BBU_MANUAL_LOGIN)

    try:
        with sync_playwright() as p:
            if login_manual_forcado:
                resultado, _ = executar_coleta_com_browser(p, site, resultado, login_manual=True)
                return resultado

            resultado, precisa_manual = executar_coleta_com_browser(p, site, resultado, login_manual=False)
            if precisa_manual and login_auto:
                print(f"{site['nome']}: CAPTCHA/login manual detectado. Abrindo navegador visivel...")
                resultado = resultado_base(site)
                resultado, _ = executar_coleta_com_browser(p, site, resultado, login_manual=True)

    except PlaywrightTimeoutError as e:
        resultado["erro"] = f"Timeout no acesso web: {limpar_erro_sensivel(e)}"
    except Exception as e:
        resultado["erro"] = limpar_erro_sensivel(e)

    return resultado
