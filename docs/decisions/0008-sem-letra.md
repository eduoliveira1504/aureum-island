# 0008 — Sem letra de música

Status: Aceita
Date: 2026-10-29
Substitui: a parte de letras da [0005](0005-musica.md) (SMTC e volume continuam valendo)

## Context

A página Música tinha uma coluna de letra (LRCLIB). Era a única chamada externa além dos links ICS, tinha cache próprio no SQLite (`lyrics_cache`) e ocupava quase metade da página.

## Decision

- **Decisão de produto: a Música fica só com o player.** Saem a busca e o cache de letras, a coluna da página, a chave `lyrics_enabled` e o switch em Geral.
- **A única chamada externa do app passa a ser o link ICS que o usuário colar.**
- **Banco:** a migração 5 faz `DROP TABLE lyrics_cache` (e o índice). A migração 3 não muda, para quem atualiza de uma versão antiga.
- **settings.json:** `lyrics_enabled` vira chave desconhecida, ignorada na leitura e apagada no próximo save.
- **Nova página Música, na largura toda (620):**
  - capa de 120 px à esquerda;
  - à direita: título 15/600, artista 13, barra de progresso com tempos, e controles (anterior, play em accent, próxima) com o volume na mesma linha.
  - O único timer é o do próximo segundo, com a página visível e tocando.
- O User-Agent dos pedidos ICS fica no `calendar_sync`, com o mesmo texto.

## Consequences

- Nenhum dado da faixa sai do computador.
- Quem quiser letra usa o próprio player.
