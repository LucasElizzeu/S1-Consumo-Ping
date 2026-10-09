# Execute este arquivo no PowerShell dentro de C:\noc_tefe
# Se der bloqueio de execução de script, rode manualmente os comandos abaixo.

py -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
