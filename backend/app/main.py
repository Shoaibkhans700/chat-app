import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, and_, text
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.deps import get_current_user
from app.models import User, Message
from app.schemas import (
    UserRegister, UserLogin, Token, UserOut,
    MessageCreate, MessageOut, HealthOut, ReadyOut,
)
from app.security import hash_password, verify_password, create_access_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-app")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup. For a real production app this would be
    # replaced by Alembic migrations run as a separate step/Job - see README.
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured.")
    yield


app = FastAPI(title="Chat App API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health / readiness — used by Kubernetes liveness/readiness probes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthOut, tags=["health"])
def health():
    """Liveness: is the process up and able to handle a request at all."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyOut, tags=["health"])
def ready(db: Session = Depends(get_db)):
    """Readiness: can we actually reach the database (RDS)."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not reachable",
        )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        or_(User.username == payload.username, User.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )
    db.refresh(user)
    return user


@app.post("/login", response_model=Token, tags=["auth"])
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(subject=user.username)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me", response_model=UserOut, tags=["auth"])
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All users except the caller, for the contact list in the chat UI."""
    return db.query(User).filter(User.id != current_user.id).order_by(User.username).all()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@app.get("/messages/{user_id}", response_model=list[MessageOut], tags=["messages"])
def get_conversation(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full conversation between the current user and `user_id`, oldest first."""
    other = db.query(User).filter(User.id == user_id).first()
    if not other:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    messages = (
        db.query(Message)
        .filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == user_id),
                and_(Message.sender_id == user_id, Message.receiver_id == current_user.id),
            )
        )
        .order_by(Message.created_at.asc())
        .all()
    )
    return messages


@app.post("/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED, tags=["messages"])
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    receiver = db.query(User).filter(User.id == payload.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")
    if receiver.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot message yourself")

    message = Message(
        sender_id=current_user.id,
        receiver_id=payload.receiver_id,
        message=payload.message,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
