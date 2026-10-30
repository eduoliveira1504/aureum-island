# 0007 — Configurações, tema da janela, início com o Windows e instância única

> Paleta clara, contornos e tela Aparência: substituídos por [0009](0009-personalizacao-igual-ao-voice.md).

Status: Aceita
Date: 2026-10-29

## Context

A janela de Configurações do Bloco 5 só tinha a seção Calendário. O Bloco 6 preenche Geral, Avisos, Foco e água e Aparência. Isso traz o tema Claro/Escuro/Sistema da janela, o atalho escolhido pelo usuário e o "Iniciar com o Windows". Com o início automático, abrir o app de novo à mão geraria dois notches e avisos em dobro.

## Decision

- **Aplicar na hora, sem botão Salvar.** `SettingsStore` guarda as configurações, grava o `settings.json` (escrita atômica) e emite as chaves que mudaram; o app aplica cada uma:
  - modo, tela cheia, antecedência (rearma o motor), som, foco, água, letras, semana, tema, accent, fundo;
  - valor inválido é recusado antes de gravar.
- **Tema da janela** (`window_theme`: `dark`, `light` ou `system`; padrão `system`):
  - vale só para a janela de Configurações; o notch continua sempre escuro;
  - "Sistema" segue `QStyleHints.colorScheme` e muda junto com o Windows por evento (`colorSchemeChanged`), sem timer;
  - a barra de título acompanha o tema via `DWMWA_USE_IMMERSIVE_DARK_MODE`.
- **Paleta clara quente:**
  - painel #FAF7F0, sidebar #F1ECE1, superfície #E8E0CF;
  - texto #1E1A14, secundário #5C5446, fraco #665D4E;
  - perigo #7A1F16 sobre #F6D5CE.
  - Contornos mais fortes que no escuro (55% em vez de 30%), senão somem no creme.
- **accent_text recebe a direção do tema:** mistura em direção ao branco no escuro e ao preto no claro (ex.: dourado vira #795E19 no claro). Um teste percorre todos os pares texto/superfície e accent_text/superfície, nos dois temas e com todos os presets, exigindo ≥ 4.5:1.
- **Atalho:**
  - "Usar padrão" volta ao Ctrl+Alt+I, e só o padrão tenta os fallbacks.
  - Um atalho escolhido que falha é recusado: o anterior continua valendo e a tela diz o motivo (em uso por outro app ou bloqueado pela regra do AltGr, ver 0003).
  - "Sem atalho" grava `hotkey: ""`; o notch abre pelo tray ou pelo hover.
  - Enquanto o campo grava uma combinação, o atalho atual fica solto (senão ele mesmo engoliria as teclas).
- **Iniciar com o Windows** (`autostart`, desligado por padrão):
  - valor "Aureum Island" em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, sem instalador e sem admin;
  - comando: `"<.venv>\Scripts\pythonw.exe" -m aureum_island`, sem janela de console;
  - ao iniciar com a opção ligada, se o caminho no registro estiver errado (pasta movida) ou sumiu, a entrada é corrigida;
  - se o registro recusar, o switch volta e a tela avisa.
  - Testado: o Python da Store escreve na chave Run real, não numa cópia virtualizada.
- **Instância única:**
  - `QLockFile` em `<dados>\instance.lock` decide quem é a primeira. Sem corrida: no Windows dois `QLocalServer` podem escutar o mesmo nome, e a trava resolve isso.
  - `QLocalServer`/`QLocalSocket` com nome fixo por usuário (`aureum-island-<usuário>`) levam o recado.
  - A segunda instância manda "open", a primeira abre o notch, e a segunda sai com código 0 antes de montar qualquer UI.
- **Durações do foco:** parado, aplica na hora; rodando ou pausado, a fase atual termina com a duração antiga e a nova vale a partir da próxima fase (`FocusModel.set_config`).

## Consequences

- Se a fase em andamento for longa, a mudança de duração só aparece quando ela acaba (escolha do Eduardo).
- Se o app for reiniciado no meio de uma fase depois de mudar a duração, a fase continua com o horário de término salvo; só o anel de progresso usa a duração nova.
- Contorno de 55% no claro: o accent fica mais presente nos botões secundários do que no escuro.
- A opção de início automático aponta para o Python do `.venv`; com o instalador (Fase 2), o comando passa a ser o executável.
