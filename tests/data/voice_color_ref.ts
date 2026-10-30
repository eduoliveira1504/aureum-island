import { inkOn, readableOn, retint, contrast } from './color.ts' // apps/desktop/src/renderer/src/lib/color.ts do Aureum Voice
const GOLD = '#E8B531'
const accents = ['#E8B531', '#8B5CF6', '#3FBF7F', '#E06A4E', '#4F8CC9', '#808080']
const dark = { rail: '#0A0908', panel: '#12110D', main: '#17150F', elevated: '#201D16', border: '#2A261D', text: '#F4EFE4', muted: '#A8A090' }
const light = { rail: '#EFE9DC', panel: '#F6F2E8', main: '#FFFFFF', elevated: '#F3EEE2', border: '#E4DCCB', text: '#1C1810', muted: '#6B6354' }
const out: any = {}
for (const a of accents) {
  const r: any = { ink: inkOn(a) }
  for (const [name, pal] of [['dark', dark], ['light', light]] as const) {
    const tinted: any = {}
    for (const [k, v] of Object.entries(pal)) tinted[k] = retint(v, a, GOLD)
    r[name] = tinted
    r[name + '_accent_text'] = readableOn(a, [tinted.rail, tinted.panel, tinted.main, tinted.elevated])
  }
  out[a] = r
}
console.log(JSON.stringify(out, null, 1))
