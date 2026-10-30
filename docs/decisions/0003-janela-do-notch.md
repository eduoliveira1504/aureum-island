# 0003 — Janela do notch

Status: Aceita
Date: 2026-10-29

## Context

O notch fica sempre por cima de tudo, no topo do monitor principal, onde também ficam as abas do navegador. Ele não pode aparecer na barra de tarefas, roubar foco ou cliques, nem gastar CPU parado. Também precisa abrir pelo teclado e sumir quando um app está em tela cheia.

## Decision

- **`Qt.Tool` + frameless + `WindowStaysOnTopHint` + `WA_TranslucentBackground` + `WA_ShowWithoutActivating`.** Tool não aparece na barra de tarefas. Com o fundo translúcido, o Windows usa uma janela em camadas (layered): os pixels fora do contorno arredondado são transparentes também para o mouse. Desenho com QPainterPath: topo reto, só os cantos de baixo arredondados, borda de 1px (accent 20%) nas laterais e na base.
- **Janela do tamanho exato do contorno, sem margem.** Ela cresce ao abrir e encolhe ao fechar. Fora do path a janela não existe, então hover e clique ficam precisos.
- **Sombra numa segunda janela, transparente a input** (`WindowTransparentForInput` = `WS_EX_TRANSPARENT`, `WindowDoesNotAcceptFocus`). Fica logo abaixo do notch no z-order (`SetWindowPos` com o notch como referência). Margem de 24px, e só existe no estado aberto. Motivo: uma margem desenhada na própria janela roubaria cliques das abas do navegador. Uma única animação atualiza as duas janelas no mesmo quadro (ver "Animação" abaixo); parada, a sombra não redesenha. Plano B, se houver descompasso visível: só escurecimento interno, sem sombra externa.
- **Hover por evento** (`enterEvent`/`leaveEvent`), sem polling do cursor. Os atrasos (120 ms para abrir, 300 ms para fechar) são timers singleShot que só existem enquanto agendados. A lógica fica em `island/state.py`, testável sem UI.
- **Foco.** Aberto por hover, o notch fecha ao tirar o mouse, e `WS_EX_NOACTIVATE` impede que clicar nele tire o foco do app do usuário. Aberto por atalho ou clique, o `WS_EX_NOACTIVATE` sai, a janela recebe foco (Tab, setas, Esc) e fecha com Esc ou perda de foco. Se o Windows negar o foco, o notch volta à regra do hover para não ficar preso aberto.
- **Atalho global com `RegisterHotKey`** (salvo em settings.json). Não é hook de teclado: o Windows só avisa quando a combinação registrada é pressionada, e o app não lê nenhuma outra tecla. Por isso não fere a regra de "sem hook global". O atalho é desregistrado ao sair.
  - **Padrão Ctrl+Alt+I.** Em teclado ABNT2, Ctrl+Alt equivale a AltGr: um atalho Ctrl+Alt+<tecla> bloqueia, em todos os apps, o caractere que o AltGr gera com aquela tecla. Por isso nenhum padrão usa Q, W, E, C, 1–6, =, [, ], / ou ; (`ALTGR_RESERVED`, coberto por teste). O padrão antigo, Ctrl+Alt+Espaço, conflitava com outro programa na máquina de desenvolvimento e é migrado (schema 2 do settings.json).
  - **Se o registro falhar**, o app tenta em ordem Ctrl+Alt+I, Ctrl+Alt+K e Ctrl+Shift+Alt+I. Grava em settings.json qual funcionou (`hotkey_active`) e o status (`registered`, `fallback`, `failed`), para a tela de Configurações mostrar o aviso. Nada quebra; sem atalho, o tray tem "Abrir".
- **Tela cheia com `SetWinEventHook`**, por evento:
  - `EVENT_SYSTEM_FOREGROUND` acompanha a janela em primeiro plano.
  - `EVENT_OBJECT_LOCATIONCHANGE` é restrito ao processo dessa janela e recriado a cada troca. Ele cobre o app que já está na frente e entra em tela cheia (F11, vídeo).
  - O callback descarta na primeira linha tudo que não for `OBJID_WINDOW` / `CHILDID_SELF` / a janela em primeiro plano, e só reinicia um singleShot de 150 ms. A comparação de retângulos roda depois, agrupada.
  - Conta como tela cheia a janela que cobre o monitor principal, exceto se estiver maximizada com barra de título (caso da barra de tarefas oculta). O desktop e a barra de tarefas são ignorados, e a própria janela do app não muda o estado.
  - Isolado em `services/fullscreen.py`; fora do Windows e nos testes é no-op.
- **Leveza.** Com o notch parado, o único timer é o singleShot do relógio na virada do minuto. Ele é rearmado também em `WM_TIMECHANGE` e na volta da suspensão. `--debug-paint` loga cada paintEvent e cada checagem de tela cheia.

## Consequences

- São duas janelas nativas para manter em sincronia. Se o descompasso aparecer em alguma máquina, o plano B está definido.
- Se o atalho escolhido e os três fallbacks estiverem em uso, o usuário precisa trocá-lo (Bloco 6). Até lá, o tray tem "Abrir".
- `ctypes` com Win32 em três módulos pequenos (`island/win32.py`, `services/hotkey.py`, `services/fullscreen.py`), todos com caminho no-op.

## Animação (revisão de 2026-10-30)

O Eduardo achou as animações "duras", principalmente ao abrir um vídeo em tela cheia. Medido no PC dele:
- o monitor roda a 240 Hz, mas a animação andava a 60 fps (o relógio padrão do Qt, 16 ms);
- cada quadro redimensionava as duas janelas nativas (~3 ms);
- na tela cheia o notch sumia e voltava sem animação.

- **Relógio na taxa do monitor** (`island/motion.py`, `FrameClock`): por tempo decorrido, com intervalo de 1000/Hz da tela principal (240 Hz -> 4 ms; 60 Hz -> 16 ms). Só existe durante a animação: parado, continuam zero timers e zero paints.
- **Geometria só no começo e no fim.** As janelas crescem uma vez para o maior quadro (com a folga do quique da mola) e voltam ao tamanho exato no fim. A cada quadro só o desenho muda.
  - O conteúdo mora num recipiente do tamanho da forma, que o revela enquanto cresce.
  - Hover e clique contam só dentro da forma.
  - Medido depois: 4 ms entre quadros e 1,8 ms por quadro (antes 16 ms e 3 ms).
- **Curvas e tempos:**

  | Movimento | Curva | Duração |
  |---|---|---|
  | Abrir e aviso entrando | mola com ζ = 0,75 (passa ~2,8% do caminho e volta; chega ao tamanho em ~160 ms) | assenta em 400 ms |
  | Fechar | cubic-bezier(0.4, 0, 0.2, 1) | 220 ms |
  | Recolher para a tela cheia | mesma curva de fechar | 180 ms |
  | Descer de volta | cubic-bezier(0.05, 0.7, 0.1, 1) | 260 ms |
  | Troca de página | mesma curva de descer | 160 ms |

  - Ao recolher para a tela cheia, a altura vai a 0 e o conteúdo some em fade.
  - Na troca de página, a página nova desliza 12 px do lado de onde veio, com fade.
  - Uma aceleração pura no fechar foi testada e descartada: segura no começo e parece travar.
- **Conteúdo junto com a forma:** o que sai some no primeiro quarto do tempo; o que entra começa aos 12% ao abrir (antes, só aos 60%).
- **Tela cheia mais rápida:** quando a janela em primeiro plano muda, a checagem é imediata. Só a mudança de tamanho/posição espera o debounce de 150 ms.

### Consequência

Durante uma animação (até 400 ms), a sobra transparente em volta do notch não deixa o clique passar para o app de baixo. Em repouso a janela tem o tamanho exato, como antes.

