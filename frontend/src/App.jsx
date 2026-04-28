import { useEffect, useState } from 'react'
import './App.css'
import {
  generate,
  renderPdf,
  uploadResume,
  listHistory,
  getHistoryItem,
  deleteHistory,
  historyPdfUrl,
} from './api.js'

const EMPTY_FORM = {
  job_title: '',
  company: '',
  job_description: '',
  preferred_provider: '',
}

export default function App() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [sourceResume, setSourceResume] = useState('')   // optional override; empty = use server default
  const [uploadName, setUploadName] = useState('')
  const [json, setJson] = useState('')                    // string in editor
  const [status, setStatus] = useState(null)              // {kind, msg}
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState([])

  useEffect(() => { refreshHistory() }, [])

  async function refreshHistory() {
    try { setHistory(await listHistory()) } catch (e) { console.error(e) }
  }

  function setField(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function onUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true); setStatus({ kind: 'info', msg: 'Extracting resume...' })
    try {
      const r = await uploadResume(file)
      setSourceResume(r.text)
      setUploadName(`${r.filename} (${r.length} chars)`)
      setStatus({ kind: 'ok', msg: 'Resume loaded.' })
    } catch (err) {
      setStatus({ kind: 'error', msg: String(err.message || err) })
    } finally { setBusy(false) }
  }

  async function onGenerate() {
    if (!form.job_title || !form.company || !form.job_description) {
      setStatus({ kind: 'error', msg: 'Fill job title, company, and JD.' })
      return
    }
    setBusy(true); setStatus({ kind: 'info', msg: 'Calling LLM...' })
    try {
      const payload = {
        job_title: form.job_title,
        company: form.company,
        job_description: form.job_description,
      }
      if (sourceResume) payload.source_resume = sourceResume
      if (form.preferred_provider) payload.preferred_provider = form.preferred_provider
      const data = await generate(payload)
      setJson(JSON.stringify(data, null, 2))
      const meta = data._meta || {}
      setStatus({ kind: 'ok', msg: `Generated via ${meta.provider || '?'} (${meta.model || '?'}). Edit JSON below, then render PDF.` })
    } catch (err) {
      setStatus({ kind: 'error', msg: String(err.message || err) })
    } finally { setBusy(false) }
  }

  async function onRender() {
    let data
    try { data = JSON.parse(json) }
    catch (e) { setStatus({ kind: 'error', msg: `Invalid JSON: ${e.message}` }); return }

    setBusy(true); setStatus({ kind: 'info', msg: 'Rendering PDF...' })
    try {
      const r = await renderPdf({
        data,
        save_to_history: true,
        job_title: form.job_title,
        company: form.company,
        job_description: form.job_description,
        source_resume: sourceResume || '(default)',
      })
      const url = URL.createObjectURL(r.blob)
      const a = document.createElement('a')
      a.href = url; a.download = r.filename; a.click()
      URL.revokeObjectURL(url)
      setStatus({ kind: 'ok', msg: `Saved as ${r.filename}.` })
      refreshHistory()
    } catch (err) {
      setStatus({ kind: 'error', msg: String(err.message || err) })
    } finally { setBusy(false) }
  }

  async function loadHistory(id) {
    setBusy(true)
    try {
      const r = await getHistoryItem(id)
      setForm({
        job_title: r.job_title || '',
        company: r.company || '',
        job_description: r.job_description || '',
        preferred_provider: '',
      })
      setSourceResume(r.source_resume === '(default)' ? '' : r.source_resume)
      setUploadName(r.source_resume === '(default)' ? '' : `(restored from history #${id})`)
      setJson(JSON.stringify(r.data, null, 2))
      setStatus({ kind: 'info', msg: `Loaded history #${id}. PDF: ` })
    } catch (err) {
      setStatus({ kind: 'error', msg: String(err.message || err) })
    } finally { setBusy(false) }
  }

  async function onDelete(id, e) {
    e.stopPropagation()
    if (!confirm(`Delete history #${id}?`)) return
    try { await deleteHistory(id); refreshHistory() }
    catch (err) { setStatus({ kind: 'error', msg: String(err.message || err) }) }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>History</h2>
        {history.length === 0 && <div className="empty">No generations yet.</div>}
        {history.map(h => (
          <div key={h.id} className="item" onClick={() => loadHistory(h.id)}>
            <div>
              <div><strong>{h.company}</strong></div>
              <div className="meta">{h.job_title}</div>
              <div className="meta">{h.created_at} · {h.provider}</div>
            </div>
            <button className="del" title="Delete" onClick={(e) => onDelete(h.id, e)}>×</button>
          </div>
        ))}
      </aside>

      <main className="main">
        <h1>Resume Generator</h1>

        <div className="card">
          <h3>Job</h3>
          <div className="row">
            <div>
              <label>Job Title</label>
              <input type="text" value={form.job_title} onChange={e => setField('job_title', e.target.value)} placeholder="e.g. Microservices Architect" />
            </div>
            <div>
              <label>Company</label>
              <input type="text" value={form.company} onChange={e => setField('company', e.target.value)} placeholder="e.g. ServiceNow" />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <label>Job Description</label>
            <textarea rows={6} value={form.job_description} onChange={e => setField('job_description', e.target.value)} placeholder="Paste the JD here..." />
          </div>
          <div style={{ marginTop: 12 }} className="row">
            <div>
              <label>Source Resume (optional)</label>
              <div className="upload-row">
                <input type="file" accept=".pdf,.docx,.txt" onChange={onUpload} />
                <span className="muted">{uploadName || 'Using server default.'}</span>
              </div>
            </div>
            <div>
              <label>Preferred Provider (optional)</label>
              <select value={form.preferred_provider} onChange={e => setField('preferred_provider', e.target.value)}>
                <option value="">Auto (Cerebras → Groq → OpenRouter)</option>
                <option value="cerebras">Cerebras</option>
                <option value="groq">Groq</option>
                <option value="openrouter">OpenRouter</option>
              </select>
            </div>
          </div>
          <div className="actions" style={{ marginTop: 14 }}>
            <button className="btn" disabled={busy} onClick={onGenerate}>
              {busy ? 'Working...' : '1. Generate JSON'}
            </button>
            {status && (
              <span className={`status ${status.kind}`}>
                {status.msg}
                {status.msg?.endsWith('PDF: ') && (
                  <a href={historyPdfUrl(history[0]?.id)} target="_blank" rel="noreferrer">download</a>
                )}
              </span>
            )}
          </div>
        </div>

        <div className="card">
          <h3>Edit JSON, then render PDF</h3>
          <textarea
            className="json-editor"
            value={json}
            onChange={e => setJson(e.target.value)}
            placeholder="Generated resume JSON appears here. Edit freely before rendering."
          />
          <div className="actions" style={{ marginTop: 10 }}>
            <button className="btn success" disabled={busy || !json} onClick={onRender}>
              {busy ? 'Working...' : '2. Render PDF'}
            </button>
            <button className="btn ghost" disabled={!json} onClick={() => {
              try { setJson(JSON.stringify(JSON.parse(json), null, 2)) }
              catch (e) { setStatus({ kind: 'error', msg: `Invalid JSON: ${e.message}` }) }
            }}>Format JSON</button>
          </div>
        </div>
      </main>
    </div>
  )
}
