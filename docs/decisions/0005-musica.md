# 0005 — Música: SMTC, volume e letras

> Letra: substituída por [0008](0008-sem-letra.md).

Status: Aceita
Date: 2026-10-29

## Context

A página Música mostra o que está tocando em qualquer app (Spotify, navegador, players) e oferece controles, volume e letra sincronizada. As regras do projeto: nada de polling, nenhum timer com o notch parado, e a LRCLIB é a única chamada externa.

## Decision

- **SMTC (`winrt-*`) numa thread própria com loop asyncio.** A API do winrt é assíncrona e os eventos chegam em threads do Windows. O serviço roda num loop asyncio dedicado, e o estado volta para a thread da UI por um signal com conexão enfileirada (a UI só lê estado aplicado na própria thread). O loop principal do Qt não muda e nenhuma lib entra.
  - Tudo por evento: troca da sessão atual, propriedades (faixa, capa), playback e linha do tempo. Parado, o loop fica bloqueado esperando evento, sem gastar CPU.
  - A posição entre eventos é `posição + (agora − last_updated)` enquanto toca, a mesma ideia do `end_at` do Foco.
  - A capa vem do stream do SMTC como bytes (PNG/JPEG); capas 16:9 de vídeo são cortadas para quadrado.
- **Volume geral do sistema com pycaw.** O SMTC não controla volume. Mudanças feitas fora do app chegam pelo `IAudioEndpointVolumeCallback`, sem polling. O dispositivo padrão é lido de novo ao abrir a página, para o caso de troca de fone.
- **Letras pela LRCLIB:**
  - **Quando busca:** só quando a faixa muda (identidade = artista, título, álbum), nunca por posição. Se a duração chega depois, a faixa não é buscada de novo.
  - **Onde busca:** `/api/get` com artista, título, álbum e duração; se não achar, ou se faltar álbum ou duração, `/api/search` como fallback, que prefere letra sincronizada com duração compatível (±3 s).
  - **User-Agent:** `AureumIsland/<versão> (https://github.com/eduoliveira1504/aureum-island)`. Pedidos pelo `QNetworkAccessManager`, assíncronos no loop do Qt, sem lib nova.
  - **Cache no SQLite** (`lyrics_cache`, migração 3):
    - letra encontrada não expira, com limite de ~20 MB (sai a menos usada);
    - "não encontrada" fica 7 dias;
    - erro de rede ou do servidor (ex.: 503 "ServerOverloaded", visto em teste real) não é guardado, e a próxima tentativa é quando a faixa tocar de novo.
  - `lyrics_enabled` em settings.json desliga as buscas.
  - Só `plainLyrics`: letra estática e rolável, sem destaque, com "letra não sincronizada" em text-dim.
- **Timers.** Só com a página Música visível e algo tocando existe um singleShot, armado para o que vier primeiro: o próximo segundo (barra e tempos) ou a próxima linha da letra. Fechado, pausado ou em outra página: zero timers.

## Consequences

- O app ganha uma thread de trabalho para a mídia, encerrada ao sair (`stop` remove os handlers e para o loop).
- A busca de letras envia artista, título, álbum e duração da faixa para a LRCLIB. É a única chamada externa e pode ser desligada.
- Players que não informam a hora da posição usam a hora do evento; a barra pode atrasar até o próximo evento do app.
