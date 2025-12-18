import { useState } from 'react'
import { Volume2, Play, Loader2, Music, FileText, Upload } from 'lucide-react'

const Tester = () => {
    const [mode, setMode] = useState('text') // 'text' or 'pdf'
    const [text, setText] = useState('Welcome to the PDF implementation of the TTS service.')
    const [file, setFile] = useState(null)
    const [provider, setProvider] = useState('google')
    const [loading, setLoading] = useState(false)
    const [audioUrl, setAudioUrl] = useState(null)
    const [logs, setLogs] = useState([])
    const [apiKey, setApiKey] = useState('')

    // API Endpoints
    const PDF_API = import.meta.env.VITE_API_PDF_URL || 'http://localhost:9200'
    const TTS_API = import.meta.env.VITE_API_TTS_URL || 'http://localhost:9202'

    // Google Settings
    const [googleVoice, setGoogleVoice] = useState('en-US-Journey-F')

    // ElevenLabs Settings
    const [elevenVoiceId, setElevenVoiceId] = useState('21m00Tcm4TlvDq8ikWAM')

    const addLog = (msg, type = 'info') => {
        const timestamp = new Date().toLocaleTimeString()
        setLogs(prev => [`[${timestamp}] ${type.toUpperCase()}: ${msg}`, ...prev])
    }

    const handleSynthesize = async () => {
        setLoading(true)
        setAudioUrl(null)

        try {
            const settings = {}
            if (provider === 'google') {
                settings.voice_name = googleVoice
                // Explicitly map common voices to language codes
                const langMap = {
                    'en-US': ['en-US-Journey-F', 'en-US-Journey-D', 'en-US-Studio-O', 'en-US-Studio-Q'],
                    'en-GB': ['en-GB-Neural2-A', 'en-GB-Wavenet-A']
                }
                settings.language_code = Object.keys(langMap).find(lang => langMap[lang].includes(googleVoice)) || 'en-US'
            } else {
                settings.voice_id = elevenVoiceId
                if (apiKey) settings.api_key = apiKey
            }

            if (mode === 'text') {
                if (!text.trim()) {
                    addLog('Text can not be empty', 'error')
                    setLoading(false)
                    return
                }
                addLog(`Synthesizing text with ${provider}...`, 'info')

                const response = await fetch(TTS_API, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, provider, settings })
                })

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: response.statusText }))
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
                }
                const data = await response.json()
                processAudioResponse(data.audio_content)

            } else {
                if (!file) {
                    addLog('Please select a PDF file', 'error')
                    setLoading(false)
                    return
                }
                addLog(`Uploading PDF and synthesizing with ${provider}...`, 'info')

                const formData = new FormData()
                formData.append('file', file)
                formData.append('tts_settings', JSON.stringify({ provider, settings }))

                const response = await fetch(PDF_API, {
                    method: 'POST',
                    body: formData
                })

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: response.statusText }))
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
                }

                const data = await response.json()
                addLog(`PDF Processed. Text Preview: ${data.text_preview}`, 'info')
                processAudioResponse(data.audio_content)
            }

        } catch (err) {
            addLog(err.message, 'error')
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const processAudioResponse = (base64Audio) => {
        addLog('Synthesis successful!', 'success')

        // Revoke previous URL to prevent memory leak
        if (audioUrl) {
            URL.revokeObjectURL(audioUrl)
        }

        const binaryString = window.atob(base64Audio)
        const bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
        }
        const blob = new Blob([bytes], { type: 'audio/mpeg' })
        const url = URL.createObjectURL(blob)
        setAudioUrl(url)
    }

    return (
        <div className="tester-container" style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
            <h1>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Music size={40} /> TTS Diagnostic Tester
                </span>
            </h1>

            <div className="card">
                <div className="mode-toggle">
                    <button
                        className={`mode-btn ${mode === 'text' ? 'active' : ''}`}
                        onClick={() => setMode('text')}
                        style={{ borderRadius: '8px 0 0 8px', width: '50%' }}
                    >
                        <FileText size={18} /> Text Mode
                    </button>
                    <button
                        className={`mode-btn ${mode === 'pdf' ? 'active' : ''}`}
                        onClick={() => setMode('pdf')}
                        style={{ borderRadius: '0 8px 8px 0', width: '50%' }}
                    >
                        <Upload size={18} /> PDF Upload
                    </button>
                </div>
                <br />

                <div className="provider-toggle">
                    <button
                        className={`provider-btn ${provider === 'google' ? 'active' : ''}`}
                        onClick={() => setProvider('google')}
                    >
                        Google Cloud
                    </button>
                    <button
                        className={`provider-btn ${provider === 'elevenlabs' ? 'active' : ''}`}
                        onClick={() => setProvider('elevenlabs')}
                    >
                        ElevenLabs
                    </button>
                </div>

                {provider === 'elevenlabs' && (
                    <div className="settings-section">
                        <label>API Key (Optional if set in Env)</label>
                        <input
                            type="password"
                            placeholder="sk-..."
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                        />

                        <label>Voice ID</label>
                        <input
                            type="text"
                            value={elevenVoiceId}
                            onChange={(e) => setElevenVoiceId(e.target.value)}
                        />
                    </div>
                )}

                {provider === 'google' && (
                    <div className="settings-section">
                        <label>Voice Name</label>
                        <select value={googleVoice} onChange={(e) => setGoogleVoice(e.target.value)}>
                            <option value="en-US-Journey-F">en-US-Journey-F (Female)</option>
                            <option value="en-US-Journey-D">en-US-Journey-D (Male)</option>
                            <option value="en-US-Studio-O">en-US-Studio-O (Female)</option>
                            <option value="en-US-Studio-Q">en-US-Studio-Q (Male)</option>
                        </select>
                    </div>
                )}

                {mode === 'text' ? (
                    <>
                        <label>Text to Synthesize</label>
                        <textarea
                            rows={5}
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', background: '#1e293b', color: 'white', border: '1px solid #475569' }}
                        />
                    </>
                ) : (
                    <>
                        <label>Upload PDF</label>
                        <div style={{ border: '2px dashed #475569', padding: '2rem', borderRadius: '8px', textAlign: 'center', marginBottom: '1rem' }}>
                            <input
                                type="file"
                                accept="application/pdf"
                                onChange={(e) => setFile(e.target.files[0])}
                                style={{ display: 'none' }}
                                id="pdf-upload"
                            />
                            <label htmlFor="pdf-upload" style={{ cursor: 'pointer', color: '#818cf8' }}>
                                {file ? file.name : "Click to Select PDF"}
                            </label>
                        </div>
                    </>
                )}

                <button onClick={handleSynthesize} disabled={loading} style={{
                    width: '100%',
                    padding: '1rem',
                    borderRadius: '8px',
                    background: '#818cf8',
                    color: 'white',
                    border: 'none',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    marginTop: '1rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.5rem'
                }}>
                    {loading ? <Loader2 className="animate-spin" /> : <Volume2 />}
                    {loading ? (mode === 'text' ? 'Synthesizing...' : 'Processing PDF...') : 'Start Processing'}
                </button>

                {audioUrl && (
                    <div className="audio-controls" style={{ marginTop: '2rem', padding: '1rem', background: '#0f172a', borderRadius: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginBottom: '1rem' }}>
                            <p className="success" style={{ margin: 0, color: '#10b981' }}>
                                <Play size={16} style={{ verticalAlign: 'middle' }} /> Audio Ready
                            </p>
                            <a
                                href={audioUrl}
                                download={`speech-${Date.now()}.mp3`}
                                className="download-btn"
                                style={{
                                    textDecoration: 'none',
                                    fontSize: '0.9rem',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    color: '#818cf8'
                                }}
                            >
                                Download MP3
                            </a>
                        </div>
                        <audio controls src={audioUrl} style={{ width: '100%' }} autoPlay />
                    </div>
                )}

                <div className="status-log" style={{ marginTop: '2rem', fontSize: '0.8rem', fontFamily: 'monospace', maxHeight: '200px', overflowY: 'auto', background: '#020617', padding: '1rem', borderRadius: '4px' }}>
                    {logs.length === 0 && <span style={{ opacity: 0.5 }}>Logs will appear here...</span>}
                    {logs.map((log, i) => (
                        <div key={i} style={{
                            color: log.includes('ERROR') ? '#f43f5e' : log.includes('SUCCESS') ? '#10b981' : '#94a3b8',
                            marginBottom: '0.25rem'
                        }}>{log}</div>
                    ))}
                </div>
            </div>
        </div>
    )
}

export default Tester
