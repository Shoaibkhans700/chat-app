import { useEffect, useRef, useState } from 'react'

function formatTime(isoString) {
  const d = new Date(isoString)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function MessageWindow({ peer, currentUser, messages, onSend, sending }) {
  const [draft, setDraft] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, peer])

  if (!peer) {
    return (
      <div className="message-window">
        <div className="empty-state">Select a user on the left to start chatting.</div>
      </div>
    )
  }

  function handleSubmit(e) {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    onSend(text)
    setDraft('')
  }

  return (
    <div className="message-window">
      <div className="message-window-header">conversation with {peer.username}</div>

      <div className="message-list" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty-state">No messages yet — say hello.</div>
        )}
        {messages.map((m) => {
          const mine = m.sender_id === currentUser.id
          return (
            <div key={m.id} className={`message-row ${mine ? 'mine' : ''}`}>
              <div>
                <div className="message-bubble">{m.message}</div>
                <div className="message-meta">{formatTime(m.created_at)}</div>
              </div>
            </div>
          )
        })}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Message ${peer.username}…`}
          maxLength={2000}
        />
        <button type="submit" disabled={sending || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
