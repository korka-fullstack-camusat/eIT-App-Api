from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..models.user import User
from ..services.auth_service import verify_password, hash_password, create_access_token, get_current_user, require_admin
from ..services.otp_service import generate_otp, verify_otp
from ..services.email_service import send_otp_email
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentification"])

RESET_TOKEN_EXPIRE_MIN = 15
RESET_TOKEN_AUDIENCE   = "reset-password"


# ── Schémas ────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    username:     str
    full_name:    str | None
    role:         str = "EDITOR"


class UserOut(BaseModel):
    id:        int
    username:  str
    full_name: str | None
    email:     str | None
    is_active: bool
    role:      str = "EDITOR"
    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username:  str
    password:  str
    full_name: str | None = None
    email:     str | None = None
    role:      str = "EDITOR"


class UserUpdate(BaseModel):
    full_name: str | None = None
    email:     str | None = None
    role:      str | None = None
    is_active: bool | None = None
    password:  str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    code:  str


class ResetPasswordRequest(BaseModel):
    reset_token:  str
    new_password: str


class ResetTokenResponse(BaseModel):
    reset_token: str


# ── Helpers ────────────────────────────────────────────────────────────────

def _create_reset_token(email: str) -> str:
    return create_access_token(
        {"sub": email, "aud": RESET_TOKEN_AUDIENCE},
        expires_delta=timedelta(minutes=RESET_TOKEN_EXPIRE_MIN),
    )


def _decode_reset_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience=RESET_TOKEN_AUDIENCE,
        )
        email: str = payload.get("sub")
        if not email:
            raise ValueError
        return email
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien de réinitialisation invalide ou expiré",
        )


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, username=user.username, full_name=user.full_name, role=user.role)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


VALID_ROLES = {"ADMIN", "EDITOR", "VIEWER"}


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Nom d'utilisateur déjà utilisé")
    role = data.role if data.role in VALID_ROLES else "EDITOR"
    user = User(
        username=data.username,
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=role,
    )
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(User).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    if data.role is not None:
        if data.role not in VALID_ROLES:
            raise HTTPException(400, f"Rôle invalide. Valeurs possibles : {', '.join(VALID_ROLES)}")
        user.role = data.role
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.email is not None:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        if len(data.password) < 6:
            raise HTTPException(400, "Le mot de passe doit contenir au moins 6 caractères")
        user.hashed_password = hash_password(data.password)

    db.commit(); db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(400, "Vous ne pouvez pas supprimer votre propre compte")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    db.delete(user); db.commit()


# ── Mot de passe oublié ────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    # Réponse identique que l'email existe ou non (sécurité)
    if user and user.is_active:
        otp = generate_otp(data.email.lower())
        try:
            send_otp_email(data.email.lower(), otp, user.full_name or user.username)
        except Exception as e:
            print(f"[WARN] Erreur envoi email : {e}")
    return {"message": "Si cet email est enregistré, un code vous a été envoyé."}


@router.post("/verify-otp", response_model=ResetTokenResponse)
def verify_otp_endpoint(data: VerifyOtpRequest):
    if not verify_otp(data.email.lower(), data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code incorrect ou expiré",
        )
    return ResetTokenResponse(reset_token=_create_reset_token(data.email.lower()))


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(data.new_password) < 6:
        raise HTTPException(400, "Le mot de passe doit contenir au moins 6 caractères")

    email = _decode_reset_token(data.reset_token)
    user  = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(404, "Utilisateur introuvable")

    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Mot de passe mis à jour avec succès"}
