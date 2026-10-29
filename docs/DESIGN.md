# Design

Visual: preto quente + dourado Aureum. Notch sempre escuro.

## Cores (tokens)
- accent (padrão Dourado): #E8B531
- on-accent (texto sobre o destaque): #0A0908 (recalcular contraste ao mudar a cor)
- notch-bg: #070605 (opções: marrom escuro, grafite)
- surface: #14110D | panel: #0D0B09 | sidebar: #090806
- text: #F1E8D3 | text-muted: #A89F88 | text-dim: #8F866F
- track (barras vazias): #2A2419
- border: accent com 20% de opacidade (notch), 14% (divisores), 30% (botões)
- danger: fundo #5A2620, texto #F6D5CE
- Destaques disponíveis (iguais ao Aureum Voice): Dourado #E8B531, Ametista #9061F9, Esmeralda #3DBE87, Brasa #E5694F, Safira #4A90D9 (os 4 últimos são estimados, conferir no repo do Voice), "Outra" com conta-gotas e campo hex.

## Tipografia
- Títulos pequenos: Cinzel, caixa alta, letter-spacing ~0.18em, 10–11px, cor accent ou text-muted.
- Resto: Inter 12–15px. Números com tabular-nums. Relógio do pomodoro 28px/600.
- Empacotar as fontes no app (não depender de internet).

## Notch
- Fechado: 190x34, canto inferior 18px, relógio (13px/600) + data (11px).
- Linha mínima: 150x6, borda inferior accent 55%. Para telas com borda grossa. Hover e avisos continuam.
- Aberto: 620 de largura, conteúdo 178 de altura + barra de páginas 46. Canto inferior 30px, borda 1px accent 20%, sem borda no topo, sombra grande.
- Barra de páginas (grid 3 colunas): marca "AUREUM ISLAND" à esquerda; ícones centrais (Música, Foco, Água, Tarefas, Calendário) 42x34, ativo em accent com traço de 2px embaixo; engrenagem à direita.
- Abre no hover, fecha ao sair. Esconde em tela cheia (configurável). Troca de página por clique, roda do mouse ou setas.

## Páginas
- Música: capa 72px, título 15/600, artista 13, barra de progresso com tempos, controles (anterior, play 42px em accent, próxima), volume. Letra à direita: linha atual em accent 17/600, vizinhas em text-dim.
- Foco: anel de progresso 132px, tempo central, "FOCO · CICLO n DE 4", 4 segmentos, botões Pausar (accent), Pular, Reiniciar.
- Água: valor grande (38px) / meta, "faltam X ml", 8 segmentos, botões +250 / +500 ml, mini gráfico por horário.
- Tarefas: lista com checkbox 20px, horário à direita (pill accent para a próxima), campo "Nova tarefa" + horário + botão adicionar.
- Calendário: mês à esquerda (hoje em accent, pontos nos dias com compromisso), agenda de hoje à direita misturando tarefas e eventos, com tipo.

## Avisos (todos do mesmo tamanho)
- 360x64, canto inferior 28px, ícone/círculo 36px à esquerda, título 13/600 + subtítulo 11, ação à direita (botão 30px de altura).
- Tipos: Hora de beber água (+250 ml), Tarefa na hora (+10 min / Feito), Foco concluído (Iniciar pausa), Evento chegando (Ver agenda).
- Duração padrão 8s, som suave opcional, opção de notificação nativa do Windows.

## Janela de Configurações
- 1000x620, sidebar 220 + conteúdo. Seções: Geral, Calendário, Avisos, Foco e água, Aparência.
- Aparência: Tema (Escuro/Claro/Sistema), Cor de destaque (bolinhas 40px com anel no selecionado), código hex, fundo do notch, prévia.
- Switches 42x24, chips de opção 32px de altura.

## Referência visual
Mockup no canvas "Aureum Island" (privado). Prints em docs/img/ (adicionar).