export default function UserList({ users, selectedUserId, onSelect }) {
  return (
    <div className="user-list">
      <div className="user-list-header">Users</div>
      {users.length === 0 && (
        <div className="user-list-empty">No other users yet. Register a second account to chat.</div>
      )}
      {users.map((u) => (
        <div
          key={u.id}
          className={`user-item ${u.id === selectedUserId ? 'active' : ''}`}
          onClick={() => onSelect(u)}
        >
          <div className="avatar">{u.username.slice(0, 2).toUpperCase()}</div>
          <div className="username">{u.username}</div>
        </div>
      ))}
    </div>
  )
}
