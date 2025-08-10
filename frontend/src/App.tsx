import { useEffect, useRef, useState } from 'react'
import './App.css'
import botIcon from './assets/bot.svg'
import userIcon from './assets/user.svg'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

type Theme = 'light' | 'dark'
type Lang = 'zh' | 'en'

function App() {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme') as Theme | null
    if (saved === 'light' || saved === 'dark') return saved
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    return prefersDark ? 'dark' : 'light'
  })
  const [lang, setLang] = useState<Lang>(() => {
    const saved = localStorage.getItem('lang') as Lang | null
    return saved === 'en' ? 'en' : 'zh'
  })
  const apiBaseUrl = 'https://qa-agent-production.up.railway.app'
  const listEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    // Apply theme to <html>
    document.documentElement.classList.remove('theme-light', 'theme-dark')
    document.documentElement.classList.add(theme === 'dark' ? 'theme-dark' : 'theme-light')
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    localStorage.setItem('lang', lang)
  }, [lang])

  useEffect(() => {
    // Initial greeting once on load
    const assistantId = crypto.randomUUID()
    const greeting = getGreeting(lang)
    setMessages([{ id: assistantId, role: 'assistant', content: '' }])
    typewrite(greeting, partial => {
      setMessages(prev => prev.map(m => (m.id === assistantId ? { ...m, content: partial } : m)))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function ask() {
    if (!question.trim() || loading) return
    if (!apiBaseUrl) {
      alert(lang === 'en' ? 'VITE_API_BASE_URL is not set' : '未配置 VITE_API_BASE_URL')
      return
    }
    const user: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question.trim(),
    }
    setMessages(prev => [...prev, user])
    setQuestion('')
    setLoading(true)
    try {
      const resp = await fetch(`${apiBaseUrl}/api/qa/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: user.content, stream: false }),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      const fullText = (data?.answer ?? JSON.stringify(data)) as string
      const assistantId = crypto.randomUUID()
      // 先插入一个空内容的助手消息
      setMessages(prev => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '' },
      ])
      // 启动打字机效果（不阻塞 UI）
      typewrite(fullText, partial => {
        setMessages(prev => prev.map(m => (m.id === assistantId ? { ...m, content: partial } : m)))
      })
    } catch (err: unknown) {
      const assistant: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: (lang === 'en' ? 'Request failed: ' : '请求失败：') + (err as Error).message,
      }
      setMessages(prev => [...prev, assistant])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      ask()
    }
  }

  return (
    <div className="container">
      <div className="header">
        <div className="brand">Token AI Q&A Agent</div>
        <div className="spacer" />
        <div className="toggle-group">
          <button title={lang === 'en' ? 'Switch Language' : '切换语言'} onClick={() => setLang(prev => (prev === 'zh' ? 'en' : 'zh'))}>
            {lang === 'zh' ? '中文' : 'EN'}
          </button>
          <button title={lang === 'en' ? 'Switch Theme' : '切换主题'} onClick={() => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'))}>
            {theme === 'dark' ? '🌙' : '☀️'}
          </button>
        </div>
      </div>
      <div className="chat-box">
        {messages.map(m => (
          <div key={m.id} className={`bubble ${m.role}`}>
            <Avatar role={m.role} />
            <div className="content">{m.content}</div>
          </div>
        ))}
        <div ref={listEndRef} />
      </div>
      <div className="input-row">
        <input
          placeholder={apiBaseUrl ? (lang === 'en' ? 'Type your question and press Enter' : '输入问题并回车') : (lang === 'en' ? 'Please set VITE_API_BASE_URL first' : '请先配置 VITE_API_BASE_URL')}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!apiBaseUrl || loading}
        />
        <button onClick={ask} disabled={!apiBaseUrl || loading}>
          {loading ? (lang === 'en' ? 'Sending…' : '发送中...') : (lang === 'en' ? 'Send' : '发送')}
        </button>
      </div>
    </div>
  )
}

export default App
function Avatar({ role }: { role: 'user' | 'assistant' }) {
  const src = role === 'assistant' ? botIcon : userIcon
  const label = role === 'assistant' ? 'bot' : 'user'
  return (
    <div className="avatar" aria-label={label}>
      <img src={src} alt={label} width={20} height={20} />
    </div>
  )
}

// 工具：打字机效果
function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function typewrite(text: string, onUpdate: (partial: string) => void, msPerChar = 20) {
  const chars = [...text]
  let buf = ''
  for (let i = 0; i < chars.length; i++) {
    buf += chars[i]
    onUpdate(buf)
    // 对中文和标点稍作停顿优化
    const ch = chars[i]
    const isPunct = /[。！？；，、,.!?;:]/.test(ch)
    await sleep(isPunct ? msPerChar * 2 : msPerChar)
  }
}

function getGreeting(lang: Lang) {
  const hour = new Date().getHours()
  if (lang === 'en') {
    if (hour < 5) return "It's late 🌌 I'm here if you need me."
    if (hour < 12) return "Good morning ☀️ What's the plan today?"
    if (hour < 14) return 'Good noon 🍱 Need a hand?'
    if (hour < 18) return 'Good afternoon 🌤️ How can I help?'
    if (hour < 22) return 'Good evening 🌙 Anything I can do?'
    return "It's late 🌌 I'm here if you need me."
  }
  if (hour < 5) return '夜深了🌌 我在这里，随时帮你。'
  if (hour < 12) return '早上好☀️ 今天想做点什么？'
  if (hour < 14) return '中午好🍱 需要我帮你吗？'
  if (hour < 18) return '下午好🌤️ 我能帮你些什么？'
  if (hour < 22) return '晚上好🌙 有什么想问的？'
  return '夜深了🌌 我在这里，随时帮你。'
}
