import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, clearToken } from '../api.js'
import UserList from '../components/UserList.jsx'
import MessageWindow from '../components/MessageWindow.jsx'

const POLL_INTERVAL_MS = 3000

export default function Chat() {
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState(null)
  const [users, setUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const selectedUserRef = useRef(null)
  selectedUserRef.current = selectedUser

  function handleAuthFailure() {
    clearToken()
    navigate('/login', { replace: true })
  }

  // Initial load: who am I, and who can I talk to.
  useEffect(() => {
    async function bootstrap() {
      try {
        const [me, userList] = await Promise.all([api.me(), api.listUsers()])
        setCurrentUser(me)
        setUsers(userList)
      } catch (err) {
        handleAuthFailure()
      }
    }
    bootstrap()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadConversation = useCallback(async (userId) => {
    try {
      const data = await api.getConversation(userId)
      // Only apply the result if the user hasn't switched conversations meanwhile.
      if (selectedUserRef.current && selectedUserRef.current.id === userId) {
        setMessages(data)
      }
    } catch (err) {
      setError(err.message)
    }
  }, [])

  // Load conversation when the selected user changes, then poll for new messages.
  useEffect(() => {
    if (!selectedUser) return
    setMessages([])
    loadConversation(selectedUser.id)

    const interval = setInterval(() => loadConversation(selectedUser.id), POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [selectedUser, loadConversation])

  async function handleSend(text) {
    if (!selectedUser) return
    setSending(true)
    setError('')
    try {
      const newMessage = await api.sendMessage(selectedUser.id, text)
      setMessages((prev) => [...prev, newMessage])
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  function handleLogout() {
    clearToken()
    navigate('/login', { replace: true })
  }

  if (!currentUser) {
    return <div className="centered-shell">Loading…</div>
  }

  return (
    <div className="chat-shell">
      <div className="chat-topbar">
        <div className="brand">
          <span className="dot" />
          chat://devops-demo
        </div>
        <div className="session-user">
          signed in as <strong>{currentUser.username}</strong>
          <button className="btn-ghost" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {error && <div className="error-banner" style={{ margin: '10px 20px 0' }}>{error}</div>}

      <div className="chat-body">
        <UserList users={users} selectedUserId={selectedUser?.id} onSelect={setSelectedUser} />
        <MessageWindow
          peer={selectedUser}
          currentUser={currentUser}
          messages={messages}
          onSend={handleSend}
          sending={sending}
        />
      </div>
    </div>
  )
}
