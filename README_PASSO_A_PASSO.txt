AUTOMACAO NOC TEFE - WEB + TELEGRAM

1) Pasta do projeto:
   C:\noc_tefe

2) Arquivo de ambiente:
   Copie .env.example para .env e preencha:

   TELEGRAM_BOT_TOKEN=TOKEN_DO_BOT
   TELEGRAM_CHAT_ID=ID_DO_GRUPO
   BBU_USER=LOGIN_DAS_BBU
   BBU_PASSWORD_DEFAULT=SENHA_PADRAO_DAS_BBU
   BBU_PASSWORD_3=SENHA_DA_BBU_3

3) Configure os sites:
   Edite config_site_web.yaml e ajuste nome, URL/IP, grupo de credencial e quais comandos devem rodar.

   s1interface: true   -> roda DSP S1INTERFACE
   nrcell: true        -> roda DSP NRCELLUENUMBER
   manual_login: auto  -> tenta escondido; se houver CAPTCHA/login, abre navegador visivel
   consumo: "117 Mb/s" -> opcional, usado apenas no boletim enquanto nao houver coleta automatica de consumo

4) Instale dependencias:
   cd C:\noc_tefe
   py -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium

5) Teste Telegram:
   python teste_telegram.py

6) Teste apenas a primeira BBU:
   python teste_web_uma_bbu.py

6.1) Teste real da BBU 1 com envio para Telegram:
   python teste_real_bbu1_telegram.py

   Se abrir o navegador, faca login manualmente, preencha o Verification code/CAPTCHA
   e pressione ENTER no PowerShell quando o terminal da BBU estiver aberto.

7) Rode a rotina completa:
   python main.py

8) Arquivos gerados:
   C:\noc_tefe\bruto   -> saida de texto das telas/comandos
   C:\noc_tefe\prints  -> prints das telas das BBU
   C:\noc_tefe\saida   -> imagem final do boletim
   C:\noc_tefe\logs    -> logs de execucao e erros

9) Agendador de Tarefas do Windows:
   Programa:
   C:\noc_tefe\venv\Scripts\python.exe

   Argumentos:
   C:\noc_tefe\main.py

   Iniciar em:
   C:\noc_tefe

OBSERVACAO:
O arquivo coleta_web.py usa seletores genericos para login e campo de comando.
Se a pagina web da BBU tiver campos diferentes, ajuste:
- tentar_login_generico()
- executar_comando_generico()



