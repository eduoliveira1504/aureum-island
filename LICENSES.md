# Licenças dos recursos

| Recurso | Arquivos | Licença |
|---|---|---|
| Fonte Sora | `src/aureum_island/assets/fonts/Sora[wght].ttf` (google/fonts, `ofl/sora`) | SIL Open Font License 1.1 (`Sora-OFL.txt`) |
| Fonte Figtree | `src/aureum_island/assets/fonts/Figtree[wght].ttf` (google/fonts, `ofl/figtree`) | SIL Open Font License 1.1 (`Figtree-OFL.txt`) |
| Ícones | `src/aureum_island/assets/icons/*.svg` | © Aureum. Desenhos próprios. |
| Sons | `src/aureum_island/assets/sounds/*.wav` | © Aureum, todos os direitos reservados. Ver abaixo. |

## Sons

**© Aureum. Todos os direitos reservados.**

Os sons são os mesmos do Aureum Voice e fazem parte da identidade da marca. Todos são originais: nenhum arquivo foi tirado de outro app, de biblioteca de sons ou de terceiros, e nenhum sample é usado.

Cada som foi sintetizado do zero por `scripts/generate-sounds.mjs`, no repositório do Aureum Voice (síntese aditiva de um sino leve, notas em Mi maior), e codificado em Ogg Vorbis com ffmpeg. A nota de copyright também está nos metadados de cada arquivo.

Os sons **não** são CC0 nem de licença aberta. Não podem ser reutilizados fora dos produtos Aureum sem permissão.

O `QSoundEffect` só toca WAV, então o Ogg do Voice foi convertido uma vez com ffmpeg para WAV PCM 16-bit, 48 kHz.

| Arquivo | Uso | Origem | Licença |
|---|---|---|---|
| `message.wav` | som dos avisos do notch | `message.ogg` do Aureum Voice (`apps/desktop/src/renderer/src/assets/sounds/`), mi agudo (E6) sobre um E5 suave | © Aureum, todos os direitos reservados |
