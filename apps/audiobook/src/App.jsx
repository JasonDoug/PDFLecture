import { useState, useRef, useEffect } from 'react'
import {
  Upload,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Settings2,
  BookOpen,
  Music,
  Download,
  CheckCircle2
} from 'lucide-react'
import Tester from './components/Tester'
import defaultCover from './assets/cover.png'

function App() {
  const [showTester, setShowTester] = useState(false)
  const [status, setStatus] = useState('idle') // 'idle', 'processing', 'ready'
  const [file, setFile] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [progress, setProgress] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  const audioRef = useRef(null)

  // API Endpoints
  const PDF_API = import.meta.env.VITE_API_PDF_URL || 'http://localhost:9200'

  if (showTester) {
    return (
      <>
        <Tester />
        <div className="footer-diagnostic">
          <button className="btn-diagnostic" onClick={() => setShowTester(false)}>
            Back to Premium Player
          </button>
        </div>
      </>
    )
  }

  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files[0]
    if (!selectedFile) return

    setFile(selectedFile)
    setStatus('processing')

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      // Default premium settings: Google US Journey Female
      formData.append('tts_settings', JSON.stringify({
        provider: 'google',
        settings: {
          voice_name: 'en-US-Journey-F',
          language_code: 'en-US'
        }
      }))

      const response = await fetch(PDF_API, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Failed to process audiobook')

      const data = await response.json()

      // Convert base64 to Blob URL
      const binaryString = window.atob(data.audio_content)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }
      const blob = new Blob([bytes], { type: 'audio/mpeg' })
      const url = URL.createObjectURL(blob)

      // Revoke previous URL to prevent memory leak
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }

      setAudioUrl(url)
      setStatus('ready')
    } catch (err) {
      alert("Error: " + err.message)
      setStatus('idle')
    }
  }

  const togglePlay = () => {
    if (isPlaying) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
    setIsPlaying(!isPlaying)
  }

  const handleTimeUpdate = () => {
    setCurrentTime(audioRef.current.currentTime)
    setProgress((audioRef.current.currentTime / audioRef.current.duration) * 100)
  }

  const skip = (amount) => {
    audioRef.current.currentTime += amount
  }

  const formatTime = (time) => {
    const mins = Math.floor(time / 60)
    const secs = Math.floor(time % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="premium-container">
      <header>
        <p className="subtitle">Audio Intelligence</p>
        <h1>The Audiobook Reader</h1>
      </header>

      {status === 'idle' && (
        <label className="upload-zone" htmlFor="pdf-input">
          <input
            type="file"
            id="pdf-input"
            accept="application/pdf"
            style={{ display: 'none' }}
            onChange={handleFileUpload}
          />
          <div className="upload-icon">
            <BookOpen size={64} strokeWidth={1} />
          </div>
          <div className="upload-text">
            <h2>Select your PDF</h2>
            <p>We'll transform your document into a premium audiobook.</p>
          </div>
        </label>
      )}

      {status === 'processing' && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <h2>Synthesizing Narration...</h2>
          <p style={{ color: '#94a3b8' }}>Our AI is reading your document with professional clarity.</p>
        </div>
      )}

      {status === 'ready' && (
        <div className="player-card">
          <img src={defaultCover} alt="Book Cover" className="book-cover" />

          <div className="track-info">
            <h3>{file?.name.replace('.pdf', '') || 'Your Audiobook'}</h3>
            <p>Narrated by AI Professor (Journey-F)</p>
          </div>

          <div className="progress-container">
            <div className="progress-bar" onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect()
              const x = e.clientX - rect.left
              const pct = x / rect.width
              audioRef.current.currentTime = pct * audioRef.current.duration
            }}>
              <div className="progress-active" style={{ width: `${progress}%` }}></div>
            </div>
            <div className="time-stamps">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration || 0)}</span>
            </div>
          </div>

          <div className="controls-main">
            <button className="btn-icon" onClick={() => skip(-15)}>
              <SkipBack size={24} fill="currentColor" />
            </button>
            <button className="btn-icon btn-play" onClick={togglePlay}>
              {isPlaying ? <Pause size={32} fill="white" /> : <Play size={32} fill="white" style={{ marginLeft: '4px' }} />}
            </button>
            <button className="btn-icon" onClick={() => skip(15)}>
              <SkipForward size={24} fill="currentColor" />
            </button>
          </div>

          <audio
            ref={audioRef}
            src={audioUrl}
            onTimeUpdate={handleTimeUpdate}
            onDurationChange={() => setDuration(audioRef.current.duration)}
            onEnded={() => setIsPlaying(false)}
            autoPlay
          />

          <div style={{ display: 'flex', gap: '1rem', width: '100%', marginTop: '1rem' }}>
            <a href={audioUrl} download={`${file?.name.replace('.pdf', '')}.mp3`} style={{ textDecoration: 'none', flex: 1 }}>
              <button className="btn-diagnostic" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                <Download size={16} /> Download MP3
              </button>
            </a>
            <button className="btn-diagnostic" onClick={() => setStatus('idle')} style={{ flex: 1 }}>
              New Audiobook
            </button>
          </div>
        </div>
      )}

      <div className="footer-diagnostic">
        <button className="btn-diagnostic" onClick={() => setShowTester(true)}>
          <Settings2 size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
          Diagnostics / TTS Tester
        </button>
      </div>
    </div>
  )
}

export default App
