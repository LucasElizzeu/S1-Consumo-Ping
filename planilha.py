import os

from PIL import Image, ImageDraw, ImageFont

from grafana_consumo import formatar_bps


def carregar_fonte(tamanho: int, bold: bool = False):
    nomes = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]

    for nome in nomes:
        try:
            return ImageFont.truetype(nome, tamanho)
        except Exception:
            pass

    return ImageFont.load_default()


def cor_do_status(status: str):
    status_lower = (status or "").lower()
    if "normal" in status_lower or "ok" in status_lower:
        return (111, 222, 151)
    if "captcha" in status_lower or "login" in status_lower:
        return (244, 204, 92)
    return (244, 91, 105)


def texto_status(item: dict) -> str:
    status = item.get("status")
    ping = item.get("ping") or {}
    if status:
        texto = status.split()[0] if status.startswith("Normal ") else status
    elif isinstance(item.get("usuarios"), int):
        texto = "Normal"
    elif item.get("erro"):
        texto = "Critico"
    else:
        texto = "Sem dado"

    if ping.get("ok") and ping.get("latencia_ms") is not None:
        return f"{texto} {ping['latencia_ms']}ms"

    if ping and not ping.get("ok"):
        return f"{texto} ping off"

    return texto


def texto_usuarios(item: dict) -> str:
    usuarios = item.get("usuarios")
    if isinstance(usuarios, int):
        return f"{usuarios} usuarios"
    if item.get("status") in ("Sem ping", "Web timeout"):
        return "N/I"
    return "-"


def texto_consumo(item: dict) -> str:
    return item.get("consumo") or "-"


def nome_site_exibicao(nome: str) -> str:
    if nome.upper().startswith("BBU "):
        numero = nome.split()[-1].zfill(2)
        return f"AM_TFE_{numero}"
    return nome


def desenhar_linha(draw, y, largura):
    draw.line((0, y, largura, y), fill=(36, 39, 45), width=1)


def gerar_imagem_boletim(cidade: str, data_hora: str, resultados: list):
    largura = 900
    linhas_sites = len(resultados)
    grupos_aau = []
    for item in resultados:
        if item.get("aaus"):
            grupos_aau.append({
                "site": nome_site_exibicao(item.get("site", "-")),
                "aaus": item["aaus"],
            })

    total_linhas_aau = sum(len(grupo["aaus"]) for grupo in grupos_aau)

    altura_sites = 110 + (linhas_sites * 47)
    altura_totais = 78
    altura_aau = 120 + (max(total_linhas_aau, 1) * 47) + (38 if grupos_aau else 0)
    altura = max(620, altura_sites + altura_totais + altura_aau + 40)

    fundo = (3, 4, 6)
    linha = (36, 39, 45)
    texto = (212, 218, 228)
    texto_fraco = (150, 156, 168)
    branco = (236, 241, 248)

    img = Image.new("RGB", (largura, altura), fundo)
    draw = ImageDraw.Draw(img)

    fonte_titulo = carregar_fonte(24, bold=True)
    fonte_header = carregar_fonte(15, bold=True)
    fonte_normal = carregar_fonte(16, bold=True)
    fonte_pequena = carregar_fonte(14, bold=True)

    data, hora = data_hora.split(" ", 1)
    hora_curta = hora.replace(":", "h")
    draw.text((0, 8), f"{cidade} - NOC | {data} - {hora_curta}", fill=branco, font=fonte_titulo)

    y = 78
    col_site = 0
    col_usuarios = 265
    col_consumo = 485
    col_status = 705

    draw.text((col_site, y), "SITES", fill=texto_fraco, font=fonte_header)
    draw.text((col_usuarios, y), "USUARIOS", fill=texto_fraco, font=fonte_header)
    draw.text((col_consumo, y), "CONSUMO", fill=texto_fraco, font=fonte_header)
    draw.text((col_status, y), "STATUS", fill=texto_fraco, font=fonte_header)
    y += 27
    desenhar_linha(draw, y, largura)

    total_usuarios = 0
    total_consumo_bps = 0.0

    for item in resultados:
        y += 17
        if isinstance(item.get("usuarios"), int):
            total_usuarios += item["usuarios"]
        if isinstance(item.get("consumo_bps"), (int, float)):
            total_consumo_bps += float(item["consumo_bps"])

        status = texto_status(item)
        cor_status = cor_do_status(status)

        draw.text((col_site, y), nome_site_exibicao(item.get("site", "-")), fill=texto, font=fonte_normal)
        draw.text((col_usuarios, y), texto_usuarios(item), fill=texto, font=fonte_normal)
        draw.text((col_consumo, y), texto_consumo(item), fill=texto, font=fonte_normal)
        draw.ellipse((col_status, y + 7, col_status + 9, y + 16), fill=cor_status)
        draw.text((col_status + 15, y), status, fill=cor_status, font=fonte_normal)

        y += 30
        desenhar_linha(draw, y, largura)

    y += 52
    total_consumo = formatar_bps(total_consumo_bps) if total_consumo_bps else "-"
    draw.text(
        (0, y),
        f"TOTAL SITES: {total_usuarios} usuarios conhecidos  |  {total_consumo}",
        fill=branco,
        font=fonte_header,
    )

    y += 72
    draw.text((0, y), "AAU", fill=branco, font=fonte_header)
    y += 46
    draw.text((0, y), "SITE", fill=texto_fraco, font=fonte_header)
    draw.text((265, y), "AAU", fill=texto_fraco, font=fonte_header)
    y += 26
    desenhar_linha(draw, y, largura)

    if grupos_aau:
        total_aau = 0
        for grupo in grupos_aau:
            for indice, aau in enumerate(grupo["aaus"]):
                y += 17
                usuarios = int(aau.get("usuarios") or 0)
                total_aau += usuarios
                site_texto = grupo["site"] if indice == 0 else ""
                draw.text((0, y), site_texto, fill=texto, font=fonte_normal)
                draw.text((265, y), f"{aau.get('aau', '-')}: {usuarios} UE/RRC", fill=texto, font=fonte_normal)
                y += 30
                desenhar_linha(draw, y, largura)

        y += 22
        draw.text((0, y), f"TOTAL AAU: {total_aau} UE/RRC", fill=branco, font=fonte_pequena)
    else:
        y += 17
        draw.text((0, y), "-", fill=texto_fraco, font=fonte_normal)
        draw.text((265, y), "Sem dados NRCELLUENUMBER", fill=texto_fraco, font=fonte_normal)

    caminho = r"C:\noc_tefe\saida\boletim_tefe.png"
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    img.save(caminho)

    return caminho
