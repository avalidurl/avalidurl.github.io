#!/usr/bin/env node
/**
 * Regenerate the downloadable CV PDF from the /cv/ page in this repo.
 * Inherits the generation criteria of gokhanturhan.com/cv
 * (gokhan-memex scripts/generate-cv-pdf.mjs): the PDF is printed by headless
 * Chrome from the same DOM the site serves, so it can never lag the page —
 * re-run this after any edit to cv/index.html, before pushing.
 * Output: cv/Gokhan_Turhan_CV.pdf
 *
 * Usage: node scripts/generate-cv-pdf.mjs
 */
import { spawn } from 'node:child_process'
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { dirname, extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')
const OUT_PDF = join(ROOT, 'cv/Gokhan_Turhan_CV.pdf')

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  'google-chrome',
  'chromium',
  'chromium-browser',
].filter(Boolean)

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
  '.json': 'application/json',
}

function findChrome() {
  for (const bin of CHROME_CANDIDATES) {
    if (bin.includes('/') && existsSync(bin)) return bin
  }
  return CHROME_CANDIDATES.find((b) => !b.includes('/')) ?? null
}

function serveRoot() {
  return createServer(async (req, res) => {
    try {
      let path = decodeURIComponent(req.url?.split('?')[0] ?? '/')
      if (path.endsWith('/')) path += 'index.html'
      const file = normalize(join(ROOT, path.replace(/^\//, '')))
      if (!file.startsWith(ROOT)) {
        res.writeHead(403)
        res.end('forbidden')
        return
      }
      await stat(file)
      const body = await readFile(file)
      res.writeHead(200, {
        'Content-Type': MIME[extname(file)] ?? 'application/octet-stream',
      })
      res.end(body)
    } catch {
      res.writeHead(404)
      res.end('not found')
    }
  })
}

function runChrome(chrome, url, outPath) {
  return new Promise((resolve, reject) => {
    const args = [
      '--headless=new',
      '--disable-gpu',
      '--no-sandbox',
      '--run-all-compositor-stages-before-draw',
      '--virtual-time-budget=15000',
      `--print-to-pdf=${outPath}`,
      '--print-to-pdf-no-header',
      url,
    ]
    const proc = spawn(chrome, args, { stdio: 'inherit' })
    proc.on('error', reject)
    proc.on('close', (code) =>
      code === 0 ? resolve() : reject(new Error(`Chrome exited ${code}`))
    )
  })
}

async function main() {
  const chrome = findChrome()
  if (!chrome) {
    console.error('✘ Chrome/Chromium not found. Set CHROME_PATH or install Google Chrome.')
    process.exit(1)
  }
  if (!existsSync(join(ROOT, 'cv/index.html'))) {
    console.error('✘ cv/index.html missing.')
    process.exit(1)
  }

  const server = serveRoot()
  await new Promise((r) => server.listen(0, '127.0.0.1', r))
  const { port } = server.address()
  const url = `http://127.0.0.1:${port}/cv/`

  console.log(`→ Printing CV via ${chrome}`)
  await runChrome(chrome, url, OUT_PDF)
  server.close()

  const { size } = await stat(OUT_PDF)
  console.log(`✓ CV PDF regenerated: ${OUT_PDF} (${Math.round(size / 1024)} KB)`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
