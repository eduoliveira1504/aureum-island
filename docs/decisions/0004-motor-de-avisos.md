# 0004 — Motor de avisos

Status: Aceita
Date: 2026-10-29

## Context

Tarefas, foco e, mais tarde, água e calendário precisam avisar na hora certa. O app fica aberto o dia todo e o PC dorme, acorda e às vezes tem o relógio alterado. A regra do projeto é não gastar CPU parado: nada de timer periódico.

## Decision

- **Provedores registráveis.** Cada um implementa `upcoming(after) -> [Due(item_type, item_id, fire_at, payload)]` e emite `changed` quando seus dados mudam. Neste bloco: tarefas (`fire_at = snoozed_until` ou `due_at − antecedência`) e foco (`end_at` da fase em andamento). Água e calendário entram registrando um provedor, sem mexer no motor.
- **Timer único.** Um `QTimer` singleShot armado para o menor `fire_at` ainda não disparado de todos os provedores, nunca periódico.
  - Limite de 6 h: se o próximo aviso estiver mais longe, o timer vence em 6 h, recalcula e rearma. Isso protege contra deriva longa do timer.
  - O relógio é uma função `now()` injetável; os testes usam um relógio falso.
- **Rearmar por evento:** quando um provedor emite `changed`, quando o horário do Windows muda (`WM_TIMECHANGE`), na volta da suspensão (`WM_POWERBROADCAST` / `PBT_APMRESUMEAUTOMATIC`) e no início do app. As mensagens chegam pelo native event filter do Bloco 1.
- **Sem duplicar.** `reminders_fired (item_type, item_id, fire_at)` é consultada antes de disparar e gravada ao disparar. Como `fire_at` faz parte da chave, adiar ("+10 min") gera um aviso novo sem conflito. Se o relógio voltar, o que já disparou não repete.
- **Avisos perdidos.** No início, na volta da suspensão e na mudança de horário, o motor faz uma recuperação (catch-up):
  - pendentes das últimas 12 h viram um único "N avisos perdidos" com "Ver" (abre Tarefas), ou o aviso normal se for só 1, com o horário original no subtítulo;
  - mais antigos que 12 h são gravados com `fired_at = NULL`: marcados, mas nunca mostrados.
  - Relógio adiantado também cai nesta regra.
  - Lembretes que perdem o sentido se atrasarem (água) usam `Due(stale_ok=False)`: na recuperação são descartados sem mostrar, nunca contam em "N avisos perdidos", e o próximo segue o intervalo normal. Na saída da tela cheia, também não entram na contagem: só o mais recente aparece.
- **Antecedência.** Global em settings.json (padrão 10 min; 0, 5, 10, 15, 30 ou 60); `remind_offset_min` na tarefa sobrescreve, e nulo usa a global. Eventos do calendário vão usar a mesma regra.
- **Apresentação fora do motor.** O motor só entrega `Due`s (`fired` ou `missed`). Quem monta o aviso é o app, e a fila do notch decide quando mostrar:
  - um aviso por vez, 8 s, pausa com o mouse em cima ou com o aviso focado;
  - espera o notch fechar;
  - em tela cheia, espera sem som e, ao sair, junta 2 ou mais num "N avisos perdidos".
- **Som do aviso:** `assets/sounds/message.wav`, o mesmo `message.ogg` do Aureum Voice (o som de mensagem nova).
  - Convertido uma vez com ffmpeg para WAV PCM 16-bit, 48 kHz, mono, porque o `QSoundEffect` só toca WAV. Os metadados de título e copyright do original foram mantidos.
  - Substitui o `chime.wav` sintetizado pelo antigo `scripts/generate_sounds.py`, que saiu.
  - Licença: © Aureum, todos os direitos reservados (ver LICENSES.md).

## Consequences

- Parado, o app tem no máximo dois timers armados: o do relógio (virada do minuto) e o do motor (próximo aviso, até 6 h).
- Cada rearmar consulta todos os provedores. Com dezenas de tarefas isso é desprezível. Se um provedor crescer muito (calendário), ele deve limitar o que devolve.
- `reminders_fired` cresce devagar (uma linha por aviso). Uma limpeza de linhas antigas pode entrar quando fizer falta.
