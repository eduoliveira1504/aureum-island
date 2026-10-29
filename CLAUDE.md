# Aureum Island

App de "Dynamic Island"/notch para Windows 10/11, da linha Aureum. Inspirado no Nusa, mas com identidade, design e código próprios (não copiar assets, mascote nem texto).

## Regras fixas
- Nome do produto: Aureum Island (não "Aurion").
- Só Windows. Python + PySide6 (Qt). pacotes winrt-* para mídia (SMTC). Dados locais (SQLite/JSON). Tokens de login no cofre do Windows (keyring).
- Tudo gratuito: sem paywall, sem conta, sem telemetria. Única chamada externa: LRCLIB (letras) e links ICS que o usuário colar.
- Sem mascote. Sem integração com o Aureum Voice. Sem overlays de volume/brilho/caps lock. Sem prateleira de arquivos. Não propor de volta sem o Eduardo pedir.
- Toda cor, fonte e medida vem de src/theme (docs/DESIGN.md). Nunca hardcoded na UI.
- Leve: nada de timers de redesenho com o notch parado. Use eventos (SMTC, QTimer só para o que precisa).
- Notch sempre escuro. Tema Claro/Escuro/Sistema vale só para a janela de Configurações.
- Acessibilidade: navegação por teclado, nomes acessíveis nos controles, contraste mínimo 4.5:1.

## Como trabalhar
- Português do Brasil, direto. Mudar só o que foi pedido.
- Antes de instalar lib nova ou mudar arquitetura, explicar o motivo.
- Decisões relevantes: um arquivo curto em docs/decisions/NNNN-titulo.md.
- Rodar testes e lint antes de dizer que terminou. Não commitar segredos.
- Estrutura sugerida: src/island (janela e animação), src/pages (música, foco, água, tarefas, calendário), src/services (mídia, lyrics, calendário, avisos, storage), src/settings, src/theme, tests/.

## Comandos (PowerShell, na raiz do repo)
- Criar o venv (Python 3.13): `python -m venv .venv`
- Instalar (app + dev): `.venv\Scripts\python -m pip install -e ".[dev]"`
- Rodar: `.venv\Scripts\python -m aureum_island` (`--debug-paint` loga cada paint e cada checagem de tela cheia)
- Testar: `.venv\Scripts\python -m pytest`
- Lint: `.venv\Scripts\ruff check .` e `.venv\Scripts\ruff format --check .`
- Pasta de dados: `%APPDATA%\Aureum Island`. A variável `AUREUM_ISLAND_DATA_DIR` troca a pasta (só testes e depuração).
- Python da Microsoft Store redireciona `%APPDATA%` para `%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.13_*\LocalCache\Roaming`. Use o Python do python.org para ver os arquivos no lugar real.

## Docs
- docs/DESIGN.md: tokens e medidas do visual.
- docs/ROADMAP.md: fases e escopo.
- docs/decisions/: decisões (NNNN-titulo.md).