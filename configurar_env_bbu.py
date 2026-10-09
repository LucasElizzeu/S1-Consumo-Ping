from getpass import getpass
from pathlib import Path


ENV = Path(r"C:\noc_tefe\.env")


def pedir_texto(rotulo: str, secreto: bool = False):
    while True:
        valor = getpass(rotulo) if secreto else input(rotulo)
        valor = valor.strip()
        if valor:
            return valor
        print("Valor vazio. Preencha para continuar.")


def atualizar_linha(conteudo: str, chave: str, valor: str):
    linha_nova = f'{chave}="{valor}"'
    linhas = conteudo.splitlines()

    for indice, linha in enumerate(linhas):
        if linha.strip().startswith(f"{chave}="):
            linhas[indice] = linha_nova
            return "\n".join(linhas) + "\n"

    if conteudo and not conteudo.endswith("\n"):
        conteudo += "\n"
    return conteudo + linha_nova + "\n"


def main():
    if not ENV.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {ENV}")

    print(f"Atualizando credenciais BBU em: {ENV}")
    usuario = pedir_texto("BBU_USER:admin ")
    senha_padrao = pedir_texto("BBU_PASSWORD_DEFAULT:v&l0s0n&t ", secreto=True)
    senha_bbu3 = pedir_texto("BBU_PASSWORD_3: ", secreto=True)

    conteudo = ENV.read_text(encoding="utf-8-sig", errors="replace")
    conteudo = atualizar_linha(conteudo, "BBU_USER", usuario)
    conteudo = atualizar_linha(conteudo, "BBU_PASSWORD_DEFAULT", senha_padrao)
    conteudo = atualizar_linha(conteudo, "BBU_PASSWORD_3", senha_bbu3)
    ENV.write_text(conteudo, encoding="utf-8")

    print("Credenciais BBU atualizadas.")
    print("Agora rode: python verificar_env.py")


if __name__ == "__main__":
    main()



