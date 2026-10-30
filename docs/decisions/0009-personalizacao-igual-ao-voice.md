# 0009 — Personalização igual ao Aureum Voice

Status: Aceita
Date: 2026-10-29
Substitui: [0002](0002-tema-e-contraste.md) e, da [0007](0007-configuracoes.md), a paleta clara, os contornos e a tela Aparência

## Context

O Island tinha paletas próprias (escura do notch, clara criada no Bloco 6), três fundos de notch, Cinzel + Inter e uma tela Aparência diferente da do Voice. A linha Aureum deve ter a mesma cara: mesmas paletas, mesmo re-tint pelo accent, mesmas fontes e a mesma tela. Referências no repo do Voice:
- `main.css`;
- `lib/color.ts`;
- `store/appearance.ts`;
- `AppearanceSettings.tsx`;
- a decisão 0003 dele.

## Decision

- **`theme/color.py` é um porte do `color.ts`**, com o mesmo comportamento:
  - `contrast`, `ink_on` (#1A1406 ou #FFFFFF), `readable_on` (direção pela luminância média dos fundos, passos de 2%) e `retint` em OKLCH (mesmas matrizes; matiz gira o ângulo entre accent e Dourado; croma escala com o do accent, sem passar do original).
  - Até o `Math.round` do JavaScript e a soma em ponto flutuante do laço foram copiados.
  - `tests/data/voice_color_ref.json` foi gerado rodando o próprio `color.ts` com o node, e os testes comparam os resultados para os 5 presets e um cinza.
- **Paletas:**
  - valores exatos do `main.css` do Voice nos dois temas (bg-rail, bg-panel, bg-main, bg-elevated, border, text, text-muted, success, danger);
  - fg-subtle = `color-mix(in oklab, text-muted 72%, bg-main)`.
  - Saem as paletas próprias do Island (inclusive a clara do Bloco 6), os fundos do notch e a chave `notch_bg`, que vira chave desconhecida, ignorada e apagada no próximo save.
- **Re-tint como no Voice:** fundos, border, text e text-muted seguem o matiz do accent; success e danger não. O `Theme` recalcula só quando o accent ou o tema mudam, nunca por frame.
- **Notch:**
  - sempre a paleta escura re-tingida, com fundo = bg-rail;
  - superfícies = bg-panel, menus = bg-main, hover = bg-elevated, track e divisores = border;
  - o contorno do notch aberto (accent 20%) e a linha mínima (accent 55%) continuam com o accent;
  - `border` vale para divisores, campos e botões secundários.
  - O tema Claro/Escuro/Sistema continua valendo só para a janela de Configurações.
- **Janela de Configurações, mapeada como o modal do Voice:** sidebar = bg-rail, conteúdo = bg-panel, campos e segmentado = bg-main, selecionado = bg-elevated.
- **Divergência proposital do Voice, por acessibilidade:**
  - Com os valores exatos, três cores usadas como texto ficam abaixo de 4.5:1:

    | Cor como texto | Escuro | Claro |
    |---|---|---|
    | fg-subtle | 3.67 a 4.35 | 2.76 a 3.34 |
    | danger | 3.22 a 3.81 | ok |
    | success | ok | 2.80 a 3.39 |

  - Os valores do Voice ficam como preenchimento.
  - Quando uma dessas cores vira texto, usa `subtle_text`, `danger_text` ou `success_text`, que passam por `readable_on` contra os quatro fundos, como o accent-text.
  - Só texto de controle desabilitado pode ficar abaixo de 4.5:1 (a WCAG isenta).
  - Um teste percorre presets × temas × pares texto/superfície e accent-text/superfície.
- **Fontes:** Sora (títulos e display) e Figtree (texto), variáveis, OFL, do google/fonts. Saem Inter e Cinzel. Os títulos pequenos em caixa alta com letter-spacing continuam, agora em Sora.
- **Tela Aparência igual à do Voice:**
  - duas colunas, com a prévia de 280 px;
  - segmentado com ícones próprios em traço (lua, sol, monitor);
  - bolinhas de 40 px com nome, ✓ e anel; "Outra" tracejada com conta-gotas.
  - O seletor livre é o QColorDialog do Qt (`DontUseNativeDialog`: o nativo do Windows não avisa enquanto arrasta e não tem "Pick Screen Color"). O EyeDropper próprio saiu.
    - Arrastando, `currentColorChanged` passa por um singleShot de 16 ms (no máximo uma prévia por frame) e só troca accent, on-accent, accent-text e hover, sem re-tint e sem salvar, como o `previewAccent` do Voice.
    - Confirmar re-tinge e salva; cancelar volta à cor salva.
  - Campo hex com 7 caracteres, monoespaçado e em maiúsculas: aplica ao digitar uma cor válida e volta ao valor atual ao perder o foco.

## Consequences

- **Em aberto: on-accent sobre o Ametista dá 4.33:1.** É a melhor das duas tintas do Voice (#1A1406; o branco dá 4.23); a tinta antiga do Island (#0A0908) dava 4.70. Os outros presets passam (Brasa 5.53, Safira 5.17). O teste trata isso como exceção conhecida até o Eduardo decidir.
- O QColorDialog é do Qt: recebe as cores do tema por stylesheet, mas os textos dele ficam em inglês (a tradução pt-BR do Qt cobre só parte).
- A prévia do seletor repinta o app inteiro a cada frame enquanto arrasta; os neutros só são re-tingidos ao confirmar.
