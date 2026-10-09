import yaml
from coleta_web import coletar_site_web

with open(r"C:\noc_tefe\config_site_web.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

site = config["sites"][0]

print(f"Testando apenas: {site['nome']} - {site['url']}")

resultado = coletar_site_web(site)

print("Resultado:")
print(f"Site: {resultado.get('site')}")
print(f"Usuários: {resultado.get('usuarios')}")
print(f"Erro: {resultado.get('erro')}")
print(f"Print S1: {resultado.get('print_s1interface')}")
print(f"Print NRCELL: {resultado.get('print_nrcell')}")
