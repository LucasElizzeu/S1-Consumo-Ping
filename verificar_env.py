from collections import defaultdict
from pathlib import Path

from dotenv import dotenv_values


ENV = Path(r"C:\noc_tefe\.env")
CHAVES = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "BBU_USER",
    "BBU_PASSWORD_DEFAULT",
    "BBU_PASSWORD_3",
]

print(f"Arquivo: {ENV}")
print(f"Existe: {ENV.exists()} | bytes: {ENV.stat().st_size if ENV.exists() else 0}")

linhas_por_chave = defaultdict(list)
if ENV.exists():
    for numero, linha in enumerate(ENV.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        texto = linha.strip()
        if not texto or texto.startswith("#") or "=" not in texto:
            continue

        chave, valor = texto.split("=", 1)
        chave = chave.strip()
        valor = valor.strip()
        if chave in CHAVES:
            sem_aspas = valor.strip().strip('"').strip("'")
            linhas_por_chave[chave].append((numero, sem_aspas))

valores = dotenv_values(ENV)

for chave in CHAVES:
    valor = valores.get(chave) or ""
    placeholder = valor.strip().upper().startswith("COLE_AQUI")
    status = "OK" if valor and not placeholder else "FALTANDO/PLACEHOLDER"
    linhas = linhas_por_chave.get(chave, [])
    linhas_txt = ", ".join(str(numero) for numero, _ in linhas) or "-"
    duplicado = "SIM" if len(linhas) > 1 else "nao"
    print(f"{chave}: {status} | tamanho={len(valor)} | linhas={linhas_txt} | duplicado={duplicado}")

    for numero, valor_linha in linhas:
        linha_placeholder = valor_linha.strip().upper().startswith("COLE_AQUI")
        print(f"  linha {numero}: tamanho={len(valor_linha)} | placeholder={linha_placeholder}")



