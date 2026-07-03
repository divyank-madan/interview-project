import { useState, useRef } from 'react'

const API_URL = 'http://127.0.0.1:8000/score'

function App() {
  const [resume, setResume] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [resumeFile, setResumeFile] = useState(null)
  const [jobFile, setJobFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const resumeInputRef = useRef(null)
  const jobInputRef = useRef(null)

  const handleResumeUpload = (event) => {
    const file = event.target.files?.[0]
    setResumeFile(file || null)
    setResume('')
    if (file && file.type.startsWith('text/')) {
      const reader = new FileReader()
      reader.onload = () => setResume(reader.result || '')
      reader.readAsText(file)
    }
  }

  const handleJobUpload = (event) => {
    const file = event.target.files?.[0]
    setJobFile(file || null)
    setJobDescription('')
    if (file && file.type.startsWith('text/')) {
      const reader = new FileReader()
      reader.onload = () => setJobDescription(reader.result || '')
      reader.readAsText(file)
    }
  }

  const clearResumeFile = () => {
    setResumeFile(null)
    setResume('')
    if (resumeInputRef.current) {
      resumeInputRef.current.value = ''
    }
  }

  const clearJobFile = () => {
    setJobFile(null)
    setJobDescription('')
    if (jobInputRef.current) {
      jobInputRef.current.value = ''
    }
  }

  const clearResumeText = () => {
    setResume('')
  }

  const clearJobText = () => {
    setJobDescription('')
  }

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const hasFile = resumeFile || jobFile
      const fetchOptions = {
        method: 'POST',
      }

      if (hasFile) {
        const formData = new FormData()
        if (resumeFile) formData.append('resume_file', resumeFile)
        if (jobFile) formData.append('job_file', jobFile)
        // Only append text fields if they have content (files will be parsed on backend)
        if (resume) formData.append('resume', resume)
        if (jobDescription) formData.append('job_description', jobDescription)
        fetchOptions.body = formData
      } else {
        fetchOptions.headers = {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        }
        fetchOptions.body = JSON.stringify({ resume, job_description: jobDescription })
      }

      const response = await fetch(API_URL, fetchOptions)
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(errorText || `API request failed (${response.status})`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message || 'Unable to score resume')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <h1>Resume Match Scorer</h1>
      <form onSubmit={submit} className="form-card">
        <label>
          Job Description
          <div className="file-input-row">
            <input
              ref={jobInputRef}
              type="file"
              accept=".txt,.md,.doc,.docx,.pdf"
              onChange={handleJobUpload}
              disabled={!!jobDescription}
            />
            {jobFile && <span className="file-name">{jobFile.name}</span>}
            {jobFile && (
              <button type="button" className="clear-file-button" onClick={clearJobFile}>
                Delete file
              </button>
            )}
            {jobDescription && !jobFile && (
              <button type="button" className="clear-file-button" onClick={clearJobText}>
                Delete text
              </button>
            )}
          </div>
          <textarea
            value={jobDescription}
            onChange={(e) => {
              const text = e.target.value
              if (jobFile) {
                clearJobFile()
              }
              setJobDescription(text)
            }}
            rows={8}
            placeholder={jobFile ? 'A job file is selected; delete it to use text input' : 'Paste the job description here'}
            required={!jobFile}
            disabled={!!jobFile}
          />
        </label>

        <label>
          Resume
          <div className="file-input-row">
            <input
              ref={resumeInputRef}
              type="file"
              accept=".txt,.md,.doc,.docx,.pdf"
              onChange={handleResumeUpload}
              disabled={!!resume}
            />
            {resumeFile && <span className="file-name">{resumeFile.name}</span>}
            {resumeFile && (
              <button type="button" className="clear-file-button" onClick={clearResumeFile}>
                Delete file
              </button>
            )}
            {resume && !resumeFile && (
              <button type="button" className="clear-file-button" onClick={clearResumeText}>
                Delete text
              </button>
            )}
          </div>
          <textarea
            value={resume}
            onChange={(e) => {
              const text = e.target.value
              if (resumeFile) {
                clearResumeFile()
              }
              setResume(text)
            }}
            rows={10}
            placeholder={resumeFile ? 'A resume file is selected; delete it to use text input' : 'Paste the resume text here'}
            required={!resumeFile}
            disabled={!!resumeFile}
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? 'Scoring...' : 'Score Resume'}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="result-box">
          <div className="result-header">
            <span>Fit:</span>
            <strong>{result.fit ? 'Yes' : 'No'}</strong>
          </div>
          <div className="result-score">Score: {result.score}%</div>
          <div className="result-details">{result.details}</div>
          {result.matched_keywords?.length > 0 && (
            <div className="matched-keywords">
              <strong>Matched keywords:</strong> {result.matched_keywords.join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
