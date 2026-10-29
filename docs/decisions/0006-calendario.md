# 0006 — Calendário: eventos locais e agendas ICS

Status: Aceita
Date: 2026-10-29

## Context

O calendário junta eventos criados no app com agendas externas (Google, Outlook) via link ICS. O link ICS secreto dá acesso à agenda inteira, então é segredo. Os avisos de evento usam o motor do Bloco 2 e não podem repetir nem disparar para coisas que já passaram.

## Decision

- **Janela de Configurações definitiva já neste bloco** (1000x620, sidebar 220), aberta pelo tray e pela engrenagem do notch. Só a seção Calendário funciona; as outras entram no Bloco 6. Sem janela temporária.
- **Links:**
  - aceita `https://` e `webcal://` (convertido para `https://`); recusa `http://` puro;
  - o link vai para o cofre do Windows (keyring) na hora de salvar;
  - na lista aparece só o domínio.
  - O link nunca vai para banco, JSON, log ou mensagem de erro. O `errorString()` do Qt pode conter a URL, por isso só o código do erro é logado.
- **Sincronização:**
  - **Quando:** ao iniciar, a cada 30 min (singleShot rearmado depois de cada rodada, só se houver agendas), na volta da suspensão e no botão "Atualizar".
  - **Cache HTTP:** `ETag` / `If-Modified-Since` quando o servidor manda; em 304 não reprocessa. Como a janela de expansão anda com o tempo, depois de 24 h sem reprocessar o pedido vai sem os cabeçalhos condicionais.
  - **Limites:** timeout de 15 s e tamanho máximo de 20 MB.
  - **Erro (rede, HTTP, ICS inválido):** mantém os eventos antigos, nada é apagado, e a lista mostra "Última atualização: <hora> · falhou".
- **Leitura:**
  - `icalendar` + `recurring-ical-events`, recorrentes expandidos só na janela de 30 dias para trás e 90 para frente, respeitando EXDATE e RECURRENCE-ID;
  - TZID de cada evento convertido para UTC no banco; horário sem fuso ("floating") é tratado como horário local;
  - dia inteiro é guardado como data (meia-noite UTC da própria data, sem conversão de fuso), com `all_day=1`.
- **Troca dos eventos da fonte numa transação só:**
  - a mesma ocorrência (uid + início) mantém o id, então mudar só o título no Google não faz o aviso disparar de novo (`reminders_fired` é por id + horário);
  - o que sumiu da agenda é removido.
- **Avisos de evento:**
  - início menos a antecedência (global ou do evento);
  - dia inteiro não tem aviso;
  - perdido conta em "N avisos perdidos" (`stale_ok=True`);
  - ação "Ver agenda" abre o Calendário no dia.
  - Eventos que chegam já com o aviso no passado (agenda recém-adicionada, evento local criado para um horário que já começou) são marcados sem mostrar, para não virar uma enxurrada de avisos.
- **Página:**
  - mês (início da semana em `week_start`, padrão domingo; a opção na UI entra no Bloco 6) e agenda do dia misturando tarefas e eventos;
  - evento local novo inline; eventos ICS são só leitura;
  - sem timers.

## Consequences

- A janela de Configurações usa por enquanto só o tema escuro; Claro/Sistema entram no Bloco 6.
- Eventos ICS fora da janela de 90 dias só aparecem quando a janela avançar (no máximo 24 h depois).
- O evento ICS não tem antecedência própria (VALARM é ignorado); usa a global.
