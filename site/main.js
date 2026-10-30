// Aureum Island landing page: the download button and a few gentle effects.
// No libraries. Everything degrades: without JS or the GitHub API the page still works.
'use strict'

const REPO = 'eduoliveira1504/aureum-island'
const RELEASES_PAGE = `https://github.com/${REPO}/releases`

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
document.documentElement.classList.add('js')

const $$ = (selector) => Array.from(document.querySelectorAll(selector))

/** fetch() that gives up after a few seconds, so a slow API never leaves things hanging. */
async function getJson(url, ms = 6000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  try {
    const res = await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } })
    if (!res.ok) throw new Error(`${url}: ${res.status}`)
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

// --- Download button ---------------------------------------------------------------

const isMobile =
  navigator.userAgentData?.mobile === true || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)

/** The installer of a release, if it has one. */
function installerOf(release) {
  if (!release || release.draft) return null
  const asset = (release.assets || []).find((a) => /\.exe$/i.test(a.name))
  return asset ? { url: asset.browser_download_url, version: release.tag_name, size: asset.size } : null
}

/** /releases/latest skips pre-releases, so the list is the fallback. */
async function latestInstaller() {
  try {
    const found = installerOf(await getJson(`https://api.github.com/repos/${REPO}/releases/latest`))
    if (found) return found
  } catch {
    // No full release yet: look through the list below.
  }
  const releases = await getJson(`https://api.github.com/repos/${REPO}/releases?per_page=10`)
  for (const release of releases) {
    const found = installerOf(release)
    if (found) return found
  }
  return null
}

const megabytes = (bytes) => `${Math.round(bytes / (1024 * 1024))} MB`

function setUpDownload() {
  const buttons = $$('[data-download]')
  const meta = document.querySelector('[data-download-meta]')

  if (isMobile) {
    for (const button of buttons) {
      button.classList.add('is-mobile')
      button.removeAttribute('href')
      button.setAttribute('aria-disabled', 'true')
      button.querySelector('[data-download-label]').textContent = 'Disponível pra Windows; abra no PC'
    }
    if (meta) meta.textContent = 'Abra esta página no computador pra baixar o instalador.'
    return
  }

  latestInstaller()
    .then((installer) => {
      if (!installer) return // the buttons already point at the releases page
      for (const button of buttons) button.href = installer.url
      const size = megabytes(installer.size)
      if (meta) meta.textContent = `${installer.version} · ${size} · Windows 10 e 11 · grátis`
      for (const el of $$('[data-download-size]')) el.textContent = `uns ${size}`
    })
    .catch(() => {
      for (const button of buttons) button.href = RELEASES_PAGE
    })
}

// --- Sections fading in, hexagon parallax --------------------------------------------

function setUpReveal() {
  const items = $$('.reveal')
  if (reducedMotion || !('IntersectionObserver' in window)) {
    for (const el of items) el.classList.add('in')
    return
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue
      entry.target.classList.add('in')
      observer.unobserve(entry.target)
    }
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' })
  for (const el of items) observer.observe(el)
}

function setUpParallax() {
  const layer = document.querySelector('.hexes')
  if (!layer || reducedMotion) return
  // The pattern repeats every 97px, so wrapping the offset keeps it seamless.
  const TILE = 97
  let queued = false
  const update = () => {
    queued = false
    const offset = (window.scrollY * 0.08) % TILE
    layer.style.transform = `translate3d(0, ${-offset}px, 0)`
  }
  window.addEventListener('scroll', () => {
    if (!queued) {
      queued = true
      requestAnimationFrame(update)
    }
  }, { passive: true })
}

// --- Screenshot lightbox ---------------------------------------------------------------

function setUpZoom() {
  const dialog = document.querySelector('[data-zoom-dialog]')
  const img = document.querySelector('[data-zoom-img]')
  if (!dialog || !img || typeof dialog.showModal !== 'function') return
  for (const shot of $$('[data-zoom]')) {
    shot.addEventListener('click', () => {
      img.src = shot.dataset.zoom
      img.alt = shot.dataset.alt || ''
      dialog.showModal()
    })
  }
  document.querySelector('[data-zoom-close]').addEventListener('click', () => dialog.close())
  // A click on the backdrop (outside the image) closes it too.
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close()
  })
}

setUpDownload()
setUpReveal()
setUpParallax()
setUpZoom()
