# 0010 — Barra própria na janela de Configurações

Status: Aceita
Date: 2026-10-30

## Context

A janela de Configurações usava a barra de título do Windows. O Eduardo quer a barra do próprio app, como a do Aureum Voice: logo + nome no fundo bg-rail e os botões de janela nas cores do tema. Uma janela só "frameless" perde o que o Windows dá de graça: sombra, cantos arredondados no Win11, encaixe nas laterais (Aero Snap), Win+setas e redimensionar pelas bordas.

## Decision

- **Para o Qt, a janela é `FramelessWindowHint`**, então ele não reserva margem de moldura. Ao mostrar, `win32.enable_custom_frame` devolve os estilos nativos (`WS_CAPTION`, `WS_THICKFRAME`, `WS_SYSMENU`, minimizar e maximizar) e estende 1 px de moldura do DWM, o que basta para a sombra.
- **`nativeEvent` (`win32.custom_frame_event`):**
  - `WM_NCCALCSIZE` devolve a janela inteira como área do app, e a barra do Windows some. Maximizada, recolhe a espessura da moldura para não passar da tela.
  - `WM_NCHITTEST` devolve as bordas e os cantos de redimensionar (faixa de 6 px lógicos, convertida pelo DPI da janela). O resto fica com o Qt.
- **Arrastar:** `QWindow.startSystemMove()` na barra, que mantém o encaixe nas laterais. Clique duplo maximiza ou restaura.
- **Botões de janela:**
  - desenho do Windows (traço de 1 px), cor `text`; hover em `bg-elevated`, e o fechar em `danger` com `on-danger`;
  - fora do Tab, como no Windows; Alt+F4, Win+setas e Alt+Espaço continuam valendo;
  - nome acessível em todos ("Minimizar", "Maximizar"/"Restaurar", "Fechar").
- A logo saiu da sidebar e foi para a barra, logo acima.
- Fora do Windows (e nos testes offscreen), a barra funciona igual, sem a parte nativa.

## Consequences

- Sem lib nova: só ctypes em `island/win32.py`.
- O hover do botão maximizar não mostra o menu de layouts de encaixe do Win11 (precisaria responder `HTMAXBUTTON`). Win+Z e arrastar até a borda continuam funcionando.
