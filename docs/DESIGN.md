# Design

Visual igual ao Aureum Voice: paletas, re-tint pelo accent e fontes. Notch sempre escuro. Ver decisão 0009.

## Cores (tokens)
Valores exatos do `main.css` do Aureum Voice, desenhados em volta do Dourado:

| Token | Escuro | Claro |
|---|---|---|
| bg-rail | #0A0908 | #EFE9DC |
| bg-panel | #12110D | #F6F2E8 |
| bg-main | #17150F | #FFFFFF |
| bg-elevated | #201D16 | #F3EEE2 |
| border | #2A261D | #E4DCCB |
| text | #F4EFE4 | #1C1810 |
| text-muted | #A8A090 | #6B6354 |
| success | #3FBF7F | #2E9E65 |
| danger | #C7363B | #C7363B |

- **fg-subtle:** `color-mix(in oklab, text-muted 72%, bg-main)`.
- **Re-tint:** fundos, border, text e text-muted seguem o matiz do accent (OKLCH, referência Dourado). success e danger não mudam. É calculado só quando o accent ou o tema mudam.
- **Cores derivadas do accent:**
  - on-accent: tinta #1A1406 ou #FFFFFF, a que contrastar mais;
  - accent-text: o accent misturado para o preto (fundo claro) ou o branco (fundo escuro) em passos de 2% até 4.5:1 contra os 4 fundos;
  - accent-hover: accent + 12% de branco (escuro) ou 10% de preto (claro), em oklab.
- **Como texto (divergência do Voice, por acessibilidade):** subtle-text, success-text e danger-text passam por `readable_on`, como o accent-text. Os valores do Voice ficam para preenchimento. Só texto de controle desabilitado pode ficar abaixo de 4.5.
- **Sobre danger:** texto #FFFFFF.
- **Destaques (iguais ao Voice):** Dourado #E8B531, Ametista #8B5CF6, Esmeralda #3FBF7F, Brasa #E06A4E, Safira #4F8CC9, e "Outra" (seletor de cor e campo hex).
- **Notch (sempre a paleta escura re-tingida):**

  | Notch | Paleta |
  |---|---|
  | fundo | bg-rail |
  | superfícies (campos, cartões) | bg-panel |
  | menus | bg-main |
  | hover/selecionado | bg-elevated |
  | track e divisores | border |
  | texto | text, text-muted e subtle-text |

  - O contorno do notch aberto (accent 20%) e a linha mínima (accent 55%) continuam com o accent.
  - border fica para divisores, campos e botões secundários.
- **Janela de Configurações (tema escolhido):**

  | Janela | Paleta |
  |---|---|
  | sidebar | bg-rail |
  | conteúdo | bg-panel |
  | campos e segmentado | bg-main |
  | selecionado e hover | bg-elevated |
  | contornos | border |

## Logo
- Logo oficial em `docs/design/brand/` (`logo.svg`, contorno; `logo-small.svg`, sólida para tamanhos pequenos).
- O app usa cópias em `assets/icons` com a cor trocada por `currentColor`: o tema pinta em accent-text, então com o Dourado fica no dourado oficial e acompanha o accent escolhido.
- Substitui o texto "AUREUM ISLAND" na barra do notch; nas Configurações fica na barra própria da janela.

## Tipografia
- **Títulos e display:** Sora. Os títulos pequenos continuam em caixa alta, letter-spacing ~0.18em, 10–11px, cor accent-text ou text-muted.
- **Texto:** Figtree 12–15px. Números com tabular-nums. Relógio do pomodoro 28px/600.
- Ambas variáveis (OFL), do repositório google/fonts, as mesmas do Voice. Ficam empacotadas no app, sem depender de internet.
- **Código hex:** fonte monoespaçada do Windows (Consolas).

## Notch
- Fechado: 190x34, canto inferior 18px, relógio (13px/600) + data (11px).
- Linha mínima: 150x6, borda inferior accent 55%. Para telas com borda grossa. Hover e avisos continuam.
- Aberto: 620 de largura, conteúdo 178 de altura + barra de páginas 46. Canto inferior 30px, borda 1px accent 20%, sem borda no topo, sombra grande.
- Barra de páginas (grid 3 colunas): logo oficial da Aureum (versão sólida, 22px, em accent-text) à esquerda; ícones centrais (Música, Foco, Água, Tarefas, Calendário) 42x34, ativo em accent com traço de 2px embaixo; engrenagem à direita.
- Abre no hover, fecha ao sair. Esconde em tela cheia (configurável). Troca de página por clique, roda do mouse ou setas.

## Movimento
- **Abrir:** mola leve, passa ~2,8% e volta (400 ms até assentar).
- **Fechar:** 220 ms, suave nas duas pontas.
- **Tela cheia:** recolhe para cima em 180 ms e desce de volta em 260 ms.
- **Troca de página:** desliza 12 px com fade, em 160 ms.
- **Ritmo:** a animação acompanha a taxa do monitor; parado, nada é redesenhado. Ver decisão 0003.

## Páginas
- Música (largura toda, 620): capa 120px à esquerda; à direita título 15/600, artista 13, barra de progresso com tempos e, na mesma linha, controles (anterior, play 42px em accent, próxima) e volume. Sem letra (ver decisão 0008).
- Foco: anel de progresso 132px, tempo central, "FOCO · CICLO n DE 4", 4 segmentos, botões Pausar (accent), Pular, Reiniciar.
- Água: valor grande (38px) / meta, "faltam X ml", 8 segmentos (cada um 1/8 da meta), botões "+copo ml" (accent) e "+2×copo ml" (copo padrão 250 ml), mini gráfico por horário da janela ativa (hora atual em accent).
- Tarefas: lista com checkbox 20px, horário à direita (pill accent para a próxima), campo "Nova tarefa" + horário + botão adicionar.
- Calendário: mês à esquerda (hoje em accent, pontos nos dias com compromisso), agenda de hoje à direita misturando tarefas e eventos, com tipo.

## Avisos (todos do mesmo tamanho)
- 360x64, canto inferior 28px, ícone/círculo 36px à esquerda, título 13/600 + subtítulo 11, ação à direita (botão 30px de altura).
- Tipos: Hora de beber água (+250 ml), Tarefa na hora (+10 min / Feito), Foco concluído (Iniciar pausa), Evento chegando (Ver agenda).
- Duração padrão 8s, som suave opcional, opção de notificação nativa do Windows.

## Janela de Configurações
- 1000x620, sidebar 220 + conteúdo.
- **Barra própria, igual à do Voice (sem a barra do Windows):**
  - 48px, fundo bg-rail;
  - logo oficial de 30px em accent-text + "Aureum Island" em Sora 15/600;
  - à direita, minimizar, maximizar/restaurar e fechar (46x48, desenho do Windows, traço de 1px em text); hover em bg-elevated, e o fechar em danger com tinta on-danger. Seções: Geral, Calendário, Avisos, Foco e água, Aparência. Tudo se aplica na hora.
- **Aparência, igual à do Voice:** duas colunas. Controles à esquerda; "Prévia" (280 px) à direita, com o notch aberto em miniatura.
  - **Tema:** segmentado Escuro, Claro e Sistema, com ícones lua, sol e monitor. Com "Sistema", a dica "Segue o modo claro/escuro do Windows."
  - **Cor de destaque:**
    - bolinhas de 40 px com o nome embaixo;
    - a selecionada tem anel na cor do texto e ✓ em on-accent;
    - "Outra" tem borda tracejada e conta-gotas, e fica preenchida e com anel quando a cor não é preset. Ela abre o QColorDialog do Qt, que tem "Pick Screen Color".
  - **Código hex:** 7 caracteres, fonte monoespaçada e maiúsculas. Aplica ao digitar uma cor válida.
  - **Dica:** "O texto sobre a cor e os links ajustam o contraste sozinhos para continuarem legíveis."
- **Controles:**
  - switches 42x24;
  - chips de opção de 32px (setas trocam a opção);
  - segmentado com 32px por opção, moldura de canto 12;
  - campos de 34px.
- **Linhas:** rótulo 13 + dica 12 em text-muted à esquerda, controle à direita, altura mínima 44. Rótulos acima de controles: 12/600, caixa alta, text-muted.

## Referência visual
Mockup no canvas "Aureum Island" (privado). Prints em docs/img/ (adicionar).