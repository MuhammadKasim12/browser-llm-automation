// API client. Base URL comes from VITE_API_BASE (set on Vercel) or '' for local dev (vite proxy).
const BASE = import.meta.env.VITE_API_BASE || ''

async function jsonOrThrow(res) {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body.detail || body.message || JSON.stringify(body)
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  return res.json()
}

export async function getSourceResume() {
  return jsonOrThrow(await fetch(`${BASE}/api/source-resume`))
}

export async function uploadResume(file) {
  const fd = new FormData()
  fd.append('file', file)
  return jsonOrThrow(await fetch(`${BASE}/api/upload-resume`, { method: 'POST', body: fd }))
}

export async function generate(payload) {
  return jsonOrThrow(await fetch(`${BASE}/api/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function renderPdf(payload) {
  const res = await fetch(`${BASE}/api/render-pdf`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { msg = (await res.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  const blob = await res.blob()
  const id = res.headers.get('X-Generation-Id')
  const cd = res.headers.get('Content-Disposition') || ''
  const m = /filename="?([^"]+)"?/.exec(cd)
  return { blob, id, filename: m ? m[1] : 'resume.pdf' }
}

export async function listHistory() {
  return jsonOrThrow(await fetch(`${BASE}/api/history`))
}

export async function getHistoryItem(id) {
  return jsonOrThrow(await fetch(`${BASE}/api/history/${id}`))
}

export function historyPdfUrl(id) {
  return `${BASE}/api/history/${id}/pdf`
}

export async function deleteHistory(id) {
  const res = await fetch(`${BASE}/api/history/${id}`, { method: 'DELETE' })
  return jsonOrThrow(res)
}
