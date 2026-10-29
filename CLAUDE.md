# Aureum Island

App de "Dynamic Island"/notch para Windows 10/11, da linha Aureum. Inspirado no Nusa, mas com identidade, design e código próprios (não copiar assets, mascote nem texto).

## Regras fixas
- Nome do produto: Aureum Island (não "Aurion").
- Só Windows. Python + PySide6 (Qt). winsdk para mídia (SMTC). Dados locais (SQLite/JSON). Tokens de login no cofre do Windows (keyring).
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

## Docs
- docs/DESIGN.md: tokens e medidas do visual.
- docs/ROADMAP.md: fases e escopo.