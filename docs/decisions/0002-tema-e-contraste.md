# 0002 — Tema e contraste

Status: Aceita
Date: 2026-10-29

## Context

O usuário escolhe a cor de destaque (presets do Aureum Voice ou qualquer hex) e o fundo do notch. Com cores livres, um texto fixo sobre o accent ou o próprio accent usado como texto podem ficar ilegíveis. A regra do projeto é contraste mínimo de 4.5:1.

## Decision

- **Tokens em `theme/tokens.py`**, espelhando o docs/DESIGN.md. Nenhuma cor, fonte ou medida fora dali.
- **Cores derivadas calculadas em `theme/color.py`** (funções puras, luminância WCAG 2.x):
  - `on_accent`: entre #0A0908 e #FFFFFF, o que tiver mais contraste com o accent.
  - `accent_text`: mistura o accent em direção ao branco em passos de 2% até atingir 4.5:1 contra todas as superfícies. Ex.: Ametista #8B5CF6 dá 4.44 sobre a surface e é clareada.
  - `with_alpha`: bordas de 20% (notch), 14% (divisores), 30% (botões) e 55% (linha mínima).
- **`Theme` (QObject)** monta tudo a partir do accent e do fundo escolhidos e emite `changed`; a UI repinta sem reiniciar.
- **Fundos do notch**: Preto #070605, Marrom escuro #1A120C e Grafite #1C1915, todos com ≥ 4.5:1 para text, text-muted e text-dim (testado).
- **Fontes empacotadas**: Inter e Cinzel variáveis (OFL), baixadas do repositório google/fonts e registradas com QFontDatabase no startup. Nada carregado da internet em runtime.

## Consequences

- O accent visto como texto pode ser um pouco mais claro que o escolhido; o accent "puro" segue nos preenchimentos.
- Adicionar uma superfície nova exige incluí-la na lista passada para `accent_text`.
- As licenças OFL ficam junto das fontes em `assets/fonts`.
