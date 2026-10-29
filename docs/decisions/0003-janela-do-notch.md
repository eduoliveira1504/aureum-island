# 0003 — Janela do notch

Status: Aceita
Date: 2026-10-29

## Context

O notch fica sempre por cima de tudo, no topo do monitor principal, onde também ficam as abas do navegador. Ele não pode aparecer na barra de tarefas, roubar foco ou cliques, nem gastar CPU parado. Também precisa abrir pelo teclado e sumir quando um app está em tela cheia.

## Decision

- **`Qt.Tool` + frameless + `WindowStaysOnTopHint` + `WA_TranslucentBackground` + `WA_ShowWithoutActivating`.** Tool não aparece na barra de tarefas. Com o fundo translúcido, o Windows usa uma janela em camadas (layered): os pixels fora do contorno arredondado são transparentes também para o mouse. Desenho com QPainterPath: topo reto, só os cantos de baixo arredondados, borda de 1px (accent 20%) nas laterais e na base.
- **Janela do tamanho exato do contorno, sem margem.** Ela cresce ao abrir e encolhe ao fechar. Fora do path a janela não existe, então hover e clique ficam precisos.
- **Sombra numa segunda janela, transparente a input** (`WindowTransparentForInput` = `WS_EX_TRANSPARENT`, `WindowDoesNotAcceptFocus`). Fica logo abaixo do notch no z-order (`SetWindowPos` com o notch como referência). Margem de 24px, e só existe no estado aberto. Motivo: uma margem desenhada na própria janela roubaria cliques das abas do navegador. Um único `QVariantAnimation` atualiza as duas geometrias no mesmo tick; parada, a sombra não redesenha. Plano B, se houver descompasso visível: só escurecimento interno, sem sombra externa.
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
