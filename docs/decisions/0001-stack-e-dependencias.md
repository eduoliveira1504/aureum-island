# 0001 — Stack e dependências

Status: Aceita
Date: 2026-10-29

## Context

O Aureum Island é um app só para Windows 10/11: uma janela sempre no topo, transparente e animada, que lê a mídia tocando, controla o volume, mostra agenda (inclusive do Google via link ICS) e guarda tudo localmente, sem conta e sem telemetria.

## Decision

- **Python 3.13 + PySide6 (Qt 6).** Janelas frameless e translúcidas, QPainter, animações e acessibilidade prontas, com DPI por monitor tratado pelo Qt. Licença LGPL, a oficial do Qt.
- **Pacotes `winrt-*` em vez do `winsdk`** para o SMTC (`Windows.Media.Control`) e streams da capa. O `winsdk` foi arquivado; os `winrt-*` são o sucessor mantido, com a mesma API e instalação por namespace.
- **pycaw para volume.** O SMTC controla só reprodução (play, pausa, faixa); volume do sistema precisa da Core Audio API.
- **icalendar + recurring-ical-events** para ler os links ICS. Agendas do Google têm muitos eventos recorrentes (RRULE, EXDATE, exceções), e expandi-los à mão é fácil de errar.
- **keyring** (Gerenciador de Credenciais do Windows) para os links ICS. O link secreto do Google dá acesso à agenda inteira, então é tratado como senha.
- **SQLite (stdlib) para dados e JSON para configurações.** Sem servidor e sem dependência extra. O banco tem migrações numeradas; o JSON é pequeno, legível e gravado de forma atômica.
- Pacotes só de Windows levam `; sys_platform == "win32"`, para os testes de lógica rodarem em outras plataformas.

## Consequences

- O app depende do runtime do Qt (~100 MB instalado). É aceitável para um app de desktop.
- As chamadas nativas que faltam (WinEventHook, RegisterHotKey) vão por `ctypes`, isoladas em `services/` e com no-op fora do Windows.
- Se os `winrt-*` mudarem de API, o impacto fica restrito ao serviço de mídia.
