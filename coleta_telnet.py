import os
import re
import asyncio
import telnetlib3
from dotenv import load_dotenv

load_dotenv(r"C:\noc_tefe\.env")

TELNET_USER = os.getenv("TELNET_USER")
TELNET_PASSWORD = os.getenv("TELNET_PASSWORD")


def extrair_usuarios_s1interface(texto: str):
    """
    Essa função é provisória.
    Depois vamos ajustar com base na saída real do DSP S1INTERFACE.
    """

    for linha in texto.splitlines():
        linha_lower = linha.lower()

        if "user" in linha_lower or "ue" in linha_lower or "number" in linha_lower:
            numeros = re.findall(r"\d+", linha)
            if numeros:
                return int(numeros[-1])

    return None


async def executar_comando_telnet(ip: str, porta: int, comandos: list):
    reader, writer = await telnetlib3.open_connection(
        host=ip,
        port=porta,
        connect_minwait=1,
        connect_maxwait=5
    )

    saida_total = ""

    # Aguarda tela inicial
    await asyncio.sleep(1)
    inicial = await reader.read(1024)
    saida_total += inicial

    # Envia usuário
    writer.write(TELNET_USER + "\n")
    await asyncio.sleep(1)
    saida_user = await reader.read(1024)
    saida_total += saida_user

    # Envia senha
    writer.write(TELNET_PASSWORD + "\n")
    await asyncio.sleep(2)
    saida_login = await reader.read(4096)
    saida_total += saida_login

    saidas_comandos = {}

    for comando in comandos:
        writer.write(comando + "\n")
        await asyncio.sleep(4)

        saida = await reader.read(12000)
        saidas_comandos[comando] = saida

    writer.write("quit\n")
    writer.close()

    return saidas_comandos


def coletar_site_telnet(site: dict):
    nome = site["nome"]
    ip = site["ip"]
    porta = site.get("porta", 23)

    resultado = {
        "site": nome,
        "ip": ip,
        "usuarios": None,
        "saida_s1interface": "",
        "saida_nrcell": "",
        "erro": None
    }

    comandos = []

    if site.get("s1interface"):
        comandos.append("DSP S1INTERFACE;")

    if site.get("nrcell"):
        comandos.append("DSP NRCELLUENNUMBER;")

    try:
        saidas = asyncio.run(executar_comando_telnet(ip, porta, comandos))

        for comando, saida in saidas.items():
            if "DSP S1INTERFACE" in comando:
                resultado["saida_s1interface"] = saida
                resultado["usuarios"] = extrair_usuarios_s1interface(saida)

                with open(fr"C:\noc_tefe\bruto\{nome}_s1interface.txt", "w", encoding="utf-8") as f:
                    f.write(saida)

            if "DSP NRCELLUENNUMBER" in comando:
                resultado["saida_nrcell"] = saida

                with open(fr"C:\noc_tefe\bruto\{nome}_nrcell.txt", "w", encoding="utf-8") as f:
                    f.write(saida)

    except Exception as e:
        resultado["erro"] = str(e)

    return resultado