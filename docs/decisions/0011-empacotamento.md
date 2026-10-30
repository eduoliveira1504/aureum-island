# 0011 — Empacotamento: PyInstaller (pasta) + Inno Setup

Status: Aceita
Date: 2026-10-30
Substitui: da [0007](0007-configuracoes.md), o comando do início automático quando instalado e a trava em arquivo da instância única

## Context

Até aqui o app só rodava pelo código (`python -m aureum_island`). Para a página de download, ele precisa de um instalador que qualquer pessoa rode sem Python, sem admin e sem conta.

## Decision

- **PyInstaller em modo pasta (`onedir`), nunca `onefile`.** O `onefile` se extrai numa pasta temporária a cada abertura, o que é mais lento e o que mais gera falso positivo de antivírus. Também sem UPX, pelo mesmo motivo.
  - Sem console, com ícone (gerado do `app.svg` em accent sobre bg-rail) e version info.
  - Inclui os assets (fontes, ícones, som) e os fusos do `tzdata` (eventos ICS com TZID).
  - Tira o que o app não usa: módulos Qt (WebEngine, 3D, QML/Quick, PDF, Charts etc.), o teclado virtual, o OpenGL por software, o ffmpeg (o `.wav` toca pelo backend do Windows) e as traduções do Qt que não são em português. Pasta de 136 para 73 MB; instalador de ~25 MB.
- **Inno Setup, instalação por usuário** (`PrivilegesRequired=lowest`):
  - em `%LOCALAPPDATA%\Programs\Aureum Island`, sem UAC;
  - atalho no Menu Iniciar, desinstalador e "Iniciar o Aureum Island" no fim;
  - arquivo `AureumIsland-Setup-<versão>.exe`, versão lida do `pyproject.toml` por `scripts/build.py`.
- **Desinstalação não apaga nada do usuário sem perguntar.** Três perguntas, todas com "Não" como resposta segura (e a resposta em modo silencioso):
  - "Iniciar com o Windows";
  - links ICS no cofre;
  - pasta `%APPDATA%\Aureum Island`.

  Quem apaga é o próprio app (`AureumIsland.exe --uninstall-cleanup [--autostart] [--secrets] [--data]`), que sabe onde fica cada coisa. Os links ICS são achados pelo nome no Gerenciador de Credenciais, sem depender do banco.
- **Instância única por mutex nomeado (`AureumIsland`)** em vez de trava em arquivo. O Python da Store redireciona `%APPDATA%`, então o app pelo código e o instalado viam pastas diferentes e abriam juntos. O mesmo nome é o `AppMutex` do Inno: instalar ou desinstalar com o app aberto pede para fechá-lo.
- **Iniciar com o Windows:** instalado (`sys.frozen`), o comando é `"<pasta>\AureumIsland.exe"`. A correção do caminho ao iniciar continua.
- **Sem assinatura digital por enquanto (Fase 2).** O Windows mostra o SmartScreen ("Mais informações" › "Executar assim mesmo") e algum antivírus pode dar falso positivo. A página explica o passo.
- **Sem atualização automática.** Seria uma chamada externa nova (checar releases), e a regra é que a única chamada externa são os links ICS. A versão nova se instala por cima, baixando de novo pela página.

## Consequences

- Cada release precisa de `scripts/build.py` rodado no Windows, com o PyInstaller (dev) e o Inno Setup 6 instalados.
- Sem atualização automática, quem instalou fica na versão antiga até voltar à página.
- Se um dia o app usar QML, PDF ou ffmpeg, o spec precisa deixar de excluí-los.
- O `AppId` do `.iss` nunca pode mudar, senão o Windows trata a próxima versão como outro app.
