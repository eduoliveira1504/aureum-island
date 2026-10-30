# 0012 — Atualização automática pelos releases do GitHub

Status: Aceita
Date: 2026-10-30
Substitui: da [0011](0011-empacotamento.md), "Sem atualização automática"

## Context

O Eduardo quer que o app se atualize sozinho, como o Aureum Voice (`electron-updater` lendo os releases do repositório público). Sem isso, quem instalou fica na versão antiga até voltar à página de download. Isso abre uma segunda chamada externa, além dos links ICS, e ele decidiu que a atualização fica sempre ligada, como no Voice.

## Decision

- **Mesmo comportamento do Voice, sem lib nova** (`services/updater.py`, `QNetworkAccessManager` e `hashlib`):
  - **Quando:** só no app instalado (`sys.frozen`). Primeira checagem 5 s depois de abrir, depois a cada 6 h.
  - **O que consulta:** `releases/latest` do repositório público, sem token. Rascunhos e pré-releases nunca são oferecidos.
  - **Versão:** comparada numericamente com a do dist-info empacotado (`version.py`).
  - **Sem internet ou GitHub fora:** tenta de novo na próxima checagem, sem avisar nada.
- **Download conferido:**
  - o instalador `AureumIsland-Setup-<versão>.exe` é baixado em segundo plano para `%LOCALAPPDATA%\Aureum Island\updates` (cache: não vai junto num perfil móvel);
  - só é aceito se o tamanho e o SHA-256 baterem com o `digest` que o GitHub publica para cada arquivo do release. Release sem `digest` é recusado.
  - Instaladores de versões já instaladas e downloads pela metade são apagados ao abrir.
- **Avisar (o "Reiniciar para atualizar" do Voice):**
  - um aviso no notch, "Atualização pronta · Versão X", com "Reiniciar";
  - um item no menu da bandeja;
  - a linha "Versão" em Configurações › Geral, com o botão.
- **Instalar:**
  - O instalador roda em modo silencioso (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`), na mesma pasta.
  - Ele é chamado pelo `__main__` só depois que o app fechou e soltou a instância única. Antes disso, o `AppMutex` do Inno acharia o app aberto e o setup silencioso desistiria.
  - **"Reiniciar":** `/RELAUNCH=1`, e uma linha nova no `[Run]` do `.iss` (`Check: ShouldRelaunch`) reabre o app no fim.
  - **Sem reiniciar:** a atualização entra quando o usuário sai pelo "Sair" da bandeja (`/RELAUNCH=0`, sem reabrir), como o `autoInstallOnAppQuit` do Voice. Desligar o Windows não instala nada.
  - O arquivo baixado pelo app não tem a marca de "veio da internet", então o SmartScreen não aparece na atualização.
- **Release:** `scripts/release.py` gera o instalador e sobe um **rascunho** com o `gh`, como o `npm run release` do Voice.
  - As notas são a seção da versão no `CHANGELOG.md`.
  - Nada chega a ninguém até o rascunho ser publicado. Ao publicar, o GitHub cria a tag `v<versão>` na main: o push vem antes.
- **CLAUDE.md:** as chamadas externas passam a ser os links ICS e os releases do GitHub.

## Consequences

- O GitHub vê o IP de quem usa o app a cada checagem (a mesma informação que vê ao abrir a página de download). Não há opção de desligar.
- Quem está na 0.1.0 precisa instalar a 0.2.0 uma vez pela página: a 0.1.0 não tem o atualizador.
- A versão de cada release precisa ser maior que a anterior, senão ninguém recebe.
- Enquanto o instalador não tiver assinatura digital, a integridade vem só do SHA-256 publicado pelo próprio GitHub (o mesmo nível do `latest.yml` do Voice).
