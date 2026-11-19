import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
type Message = {
  role: 'user' | 'assistant'
  content: string
}

type Conversation = {
  conversation_id: number
  created_at: string
}

type ChatbotProps = {
  onAppointmentsChanged?: () => void
}

function Chatbot({ onAppointmentsChanged }: ChatbotProps) {

  const chatContainerRef = useRef<HTMLDivElement>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<number | null>(() => {
  const savedId = sessionStorage.getItem('active_conversation_id')

  if (!savedId) return null

  const id = Number(savedId)

  return Number.isSafeInteger(id) && id > 0 ? id : null
})
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const container = chatContainerRef.current

    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages, loading])

  useEffect(() => {
  const controller = new AbortController()

  async function loadConversations() {
    const token = sessionStorage.getItem('access_token')

    if (!token) return

    try {
      const response = await fetch(
        'http://127.0.0.1:8000/conversations',
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: controller.signal,
        }
      )


if (!response.ok) {
    throw new Error(`Chat request failed (${response.status})`)
}

      const data = await response.json()

      if (!Array.isArray(data.conversations)) {
        throw new Error('Invalid conversations response')
      }

      if (!controller.signal.aborted) {
        setConversations(data.conversations)
      }
    } catch (err) {
      if (controller.signal.aborted) return

      setError(
        err instanceof Error
          ? err.message
          : 'Could not load conversations'
      )
    }
  }


  void loadConversations()

  return () => controller.abort()
}, [])

useEffect(() => {
  if (conversationId === null) return

  void openConversation(conversationId)

  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [])

async function openConversation(id: number) {
  if (loading) return

  const token = sessionStorage.getItem('access_token')

  if (!token) {
    setError('You must be logged in to open a conversation.')
    return
  }

  setError('')
  setLoading(true)

  try {
    const response = await fetch(
      `http://127.0.0.1:8000/conversations/${id}/messages`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    )

    if (!response.ok) {
      throw new Error(
        `Failed to load conversation (${response.status})`
      )
    }

    const data = await response.json()

    if (
      data.conversation_id !== id ||
      !Array.isArray(data.messages) ||
      !data.messages.every(
        (message: Message) =>
          (message.role === 'user' ||
            message.role === 'assistant') &&
          typeof message.content === 'string'
      )
    ) {
      throw new Error('Invalid conversation data received from server')
    }

    setConversationId(id)
sessionStorage.setItem('active_conversation_id', String(id))
setMessages(data.messages)
    setInput('')

  } catch (err) {
    setError(
      err instanceof Error
        ? err.message
        : 'Could not open conversation'
    )
  } finally {
    setLoading(false)
  }
}

  async function startNewConversation() {
  if (loading) return

  const token = sessionStorage.getItem('access_token')

  if (!token) {
    setError('You must be logged in to start a new conversation.')
    return
  }

  setError('')
  setLoading(true)

  try {
    const response = await fetch('http://127.0.0.1:8000/conversations', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to create conversation (${response.status})`)
    }

    const data = await response.json()

    if (
      typeof data.conversation_id !== 'number' ||
      !Number.isInteger(data.conversation_id) ||
      data.conversation_id <= 0
    ) {
      throw new Error('Invalid conversation ID received from server')
    }

    setConversationId(data.conversation_id)
    sessionStorage.setItem(
  'active_conversation_id',
  String(data.conversation_id)
)

setConversations((previous) => [
  {
    conversation_id: data.conversation_id,
    created_at: new Date().toISOString(),
  },
  ...previous,
])

setMessages([])
setInput('')

  } catch (err) {
    setError(
      err instanceof Error
        ? err.message
        : 'Could not start a new conversation'
    )
  } finally {
    setLoading(false)
  }
}

  async function sendMessage(event: React.SubmitEvent<HTMLFormElement>) {
  event.preventDefault()

  const message = input.trim()
  if (!message || loading) return

  const token = sessionStorage.getItem('access_token')

  if (!token) {
    setError('You must be logged in to use the chatbot.')
    return
  }

  setError('')
  setLoading(true)

  let activeConversationId = conversationId

  try {
    // Create a conversation automatically if none is selected.
    if (activeConversationId === null) {
      const createResponse = await fetch(
        'http://127.0.0.1:8000/conversations',
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      if (!createResponse.ok) {
        throw new Error(
          `Failed to create conversation (${createResponse.status})`
        )
      }

      const conversation = await createResponse.json()

      if (
        typeof conversation.conversation_id !== 'number' ||
        !Number.isInteger(conversation.conversation_id) ||
        conversation.conversation_id <= 0
      ) {
        throw new Error('Invalid conversation ID received from server')
      }

      activeConversationId = conversation.conversation_id
      setConversationId(activeConversationId)
      activeConversationId = conversation.conversation_id
        setConversationId(activeConversationId)

        sessionStorage.setItem(
        'active_conversation_id',
         String(activeConversationId)
)
    }

    // Send the message to the selected SQLite conversation.
    const response = await fetch(
      `http://127.0.0.1:8000/conversations/${activeConversationId}/chat`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message }),
      }
    )

    if (response.status === 429) {
    const retryAfter = Number(
        response.headers.get('Retry-After') ?? '60'
    )

    const seconds = Number.isFinite(retryAfter)
        ? Math.max(0, Math.ceil(retryAfter))
        : 60

    throw new Error(
        `Du har nået grænsen på 10 beskeder pr. minut. ` +
        `Prøv igen om ${seconds} sekunder.`
    )
}

if (!response.ok) {
    throw new Error(`Chat request failed (${response.status})`)
}

    const data = await response.json()

    if (typeof data.response !== 'string' || !data.response.trim()) {
      throw new Error('Unexpected response format from AI agent')
    }

    // Display the messages only after the request succeeds.
    setMessages((previous) => [
  ...previous,
  { role: 'user', content: message },
  { role: 'assistant', content: data.response },
])

setInput('')

// Notify the dashboard to refresh appointments
onAppointmentsChanged?.()

  } catch (err) {
    setError(
      err instanceof Error ? err.message : 'Something went wrong'
    )
  } finally {
    setLoading(false)
  }
}


  return (
    <section className="chatbot-layout">
      <h2>🤖 AI Service Assistant</h2>

      <div className="chatbot-columns">
        <aside className="chatbot-sidebar">
          <h3>📁 Previous Conversations</h3>

          {conversations.length === 0 ? (
            <p>No previous conversations found.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {conversations.map((conversation) => (
                <button
                  key={conversation.conversation_id}
                  type="button"
                  onClick={() => openConversation(conversation.conversation_id)}
                  disabled={loading}
                  style={{
                    padding: '10px',
                    textAlign: 'left',
                    backgroundColor:
                      conversationId === conversation.conversation_id
                        ? '#2563eb'
                        : '#374151',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                  }}
                >
                  💬 Conversation #{conversation.conversation_id}
                </button>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={startNewConversation}
            disabled={loading}
            style={{
              padding: '10px 16px',
              backgroundColor: loading ? '#6b7280' : '#2563eb',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: loading ? 'not-allowed' : 'pointer',
              marginTop: '16px',
            }}
          >
            + New Conversation
          </button>
        </aside>

        <div className="chatbot-main">
          <div
            ref={chatContainerRef}
            aria-live="polite"
            style={{
              border: '1px solid #374151',
              borderRadius: '12px',
              padding: '20px',
              height: '450px',
              overflowY: 'auto',
              backgroundColor: '#111827',
              marginBottom: '15px',
            }}
          >
            {messages.length === 0 && (
              <p>Hi! How can I help you with your vehicle today?</p>
            )}

            {messages.map((message, index) => {
              const isUser = message.role === 'user'

              return (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    justifyContent: isUser ? 'flex-end' : 'flex-start',
                    marginBottom: '16px',
                  }}
                >
                  <div
                    style={{
                      maxWidth: '80%',
                      padding: '12px 16px',
                      borderRadius: isUser
                        ? '16px 16px 4px 16px'
                        : '16px 16px 16px 4px',
                      backgroundColor: isUser ? '#2563eb' : '#374151',
                      color: '#ffffff',
                      textAlign: 'left',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        marginBottom: '6px',
                        opacity: 0.75,
                      }}
                    >
                      {isUser ? 'You' : '🤖 Assistant'}
                    </div>

                    {isUser ? (
                      <div style={{ whiteSpace: 'pre-wrap' }}>
                        {message.content}
                      </div>
                    ) : (
                      <div className="assistant-message">
                        <ReactMarkdown>
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {loading && <p>Assistant is thinking...</p>}
          </div>

          {error && (
            <p role="alert" style={{ color: 'red' }}>
              {error}
            </p>
          )}

          <form
            onSubmit={sendMessage}
            style={{
              display: 'flex',
              gap: '10px',
              width: '100%',
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask me anything about your vehicle..."
              disabled={loading}
              style={{
                flex: 1,
                minWidth: 0,
                padding: '14px 16px',
                borderRadius: '10px',
                border: '1px solid #374151',
                backgroundColor: '#1f2937',
                color: '#ffffff',
                fontSize: '14px',
                outline: 'none',
              }}
            />

            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                padding: '12px 22px',
                borderRadius: '10px',
                border: 'none',
                backgroundColor:
                  loading || !input.trim() ? '#4b5563' : '#2563eb',
                color: '#ffffff',
                fontWeight: 600,
                cursor:
                  loading || !input.trim() ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? 'Thinking...' : 'Send ➤'}
            </button>
          </form>
        </div>
      </div>
    </section>
  )
  }

export default Chatbot
