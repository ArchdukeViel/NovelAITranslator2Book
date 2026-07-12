"""Auth service — registration, login, password reset, email verification, OAuth."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from novelai.api.auth.google_oauth import GoogleOAuthProfile
from novelai.api.auth.passwords import hash_password, verify_password
from novelai.db.models.users import EmailVerificationToken, PasswordResetToken, User
from novelai.services.email import AuthEmailService

logger = logging.getLogger(__name__)

_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LENGTH = 10
_MAX_PASSWORD_LENGTH = 256
_PASSWORD_RESET_TOKEN_BYTES = 32
_PASSWORD_RESET_EXPIRES_MINUTES = 60
_EMAIL_VERIFICATION_TOKEN_BYTES = 32
_EMAIL_VERIFICATION_EXPIRES_HOURS = 24


class AuthService:
    """Business logic for public user authentication and account management."""

    def __init__(self, *, db_session: Session, mailer: AuthEmailService | None = None) -> None:
        self.db_session = db_session
        self.mailer = mailer

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def validate_email(email: str) -> str:
        normalized = AuthService.normalize_email(email)
        if len(normalized) > 255 or not _EMAIL_RE.match(normalized):
            raise ValueError("Invalid email address.")
        return normalized

    @staticmethod
    def validate_password(password: str) -> None:
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")
        if len(password) > _MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at most {_MAX_PASSWORD_LENGTH} characters.")

    @staticmethod
    def new_password_reset_token() -> str:
        return secrets.token_urlsafe(_PASSWORD_RESET_TOKEN_BYTES)

    @staticmethod
    def hash_password_reset_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def new_email_verification_token() -> str:
        return secrets.token_urlsafe(_EMAIL_VERIFICATION_TOKEN_BYTES)

    @staticmethod
    def hash_email_verification_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def is_expired(expires_at: datetime) -> bool:
        now = datetime.now(UTC)
        if expires_at.tzinfo is None:
            return expires_at <= now.replace(tzinfo=None)
        return expires_at <= now

    # -- registration -----------------------------------------------------------

    def register(self, email: str, password: str, display_name: str | None = None) -> dict[str, Any]:
        email = self.validate_email(email)
        self.validate_password(password)

        existing = self.db_session.query(User).filter(func.lower(User.email) == email).one_or_none()
        if existing is not None:
            raise ValueError("An account already exists for this email.")

        if display_name and display_name.strip() == "":
            display_name = None

        now = datetime.now(UTC)
        user = User(
            email=email,
            display_name=display_name,
            role="user",
            auth_provider="password",
            password_hash=hash_password(password),
            is_active=True,
            last_login_at=now,
        )
        self.db_session.add(user)
        self.db_session.flush()

        raw_token = self.new_email_verification_token()
        self.db_session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=self.hash_email_verification_token(raw_token),
                created_at=now,
                expires_at=now + timedelta(hours=_EMAIL_VERIFICATION_EXPIRES_HOURS),
            )
        )
        self.db_session.flush()
        self._deliver_email_verification_email(user.email, raw_token, user.id)

        return {"user_id": user.id, "email": user.email, "role": user.role}

    # -- password login ---------------------------------------------------------

    def password_login(self, email: str, password: str) -> dict[str, Any]:
        email = self.normalize_email(email)
        if not email or len(email) > 255:
            raise ValueError("Invalid email or password.")

        user = self.db_session.query(User).filter(func.lower(User.email) == email).one_or_none()
        if (
            user is None
            or not user.is_active
            or user.role == "owner"
            or not user.password_hash
            or not verify_password(password, user.password_hash)
        ):
            raise ValueError("Invalid email or password.")

        user.last_login_at = datetime.now(UTC)
        self.db_session.flush()
        return {"user_id": user.id, "email": user.email, "role": user.role}

    # -- password reset ---------------------------------------------------------

    def request_password_reset(self, email: str, ip: str | None = None, user_agent: str | None = None) -> None:
        try:
            email = self.validate_email(email)
        except ValueError:
            return

        user = self.db_session.query(User).filter(func.lower(User.email) == email).one_or_none()
        if (
            user is None
            or not user.is_active
            or user.role != "user"
            or user.auth_provider != "password"
            or not user.password_hash
        ):
            return

        now = datetime.now(UTC)
        self.db_session.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).update({"used_at": now}, synchronize_session=False)

        raw_token = self.new_password_reset_token()
        self.db_session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=self.hash_password_reset_token(raw_token),
                created_at=now,
                expires_at=now + timedelta(minutes=_PASSWORD_RESET_EXPIRES_MINUTES),
                request_ip=ip,
                user_agent=user_agent,
            )
        )
        self.db_session.flush()
        self._deliver_password_reset_email(user.email, raw_token, user.id)

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        self.validate_password(new_password)
        token = token.strip()
        if not token:
            raise ValueError("Invalid or expired reset token.")

        token_hash = self.hash_password_reset_token(token)
        reset_token = self.db_session.query(PasswordResetToken).filter_by(token_hash=token_hash).one_or_none()
        if reset_token is None or reset_token.used_at is not None or self.is_expired(reset_token.expires_at):
            raise ValueError("Invalid or expired reset token.")

        user = self.db_session.get(User, reset_token.user_id)
        if (
            user is None
            or not user.is_active
            or user.role != "user"
            or user.auth_provider != "password"
            or not user.password_hash
        ):
            raise ValueError("Invalid or expired reset token.")

        now = datetime.now(UTC)
        user.password_hash = hash_password(new_password)
        reset_token.used_at = now
        self.db_session.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.id != reset_token.id,
        ).update({"used_at": now}, synchronize_session=False)
        self.db_session.flush()

    # -- email verification -----------------------------------------------------

    def request_email_verification(self, email: str, ip: str | None = None, user_agent: str | None = None) -> None:
        try:
            email = self.validate_email(email)
        except ValueError:
            return

        user = self.db_session.query(User).filter(func.lower(User.email) == email).one_or_none()
        if (
            user is None
            or not user.is_active
            or user.role != "user"
            or user.auth_provider != "password"
            or not user.password_hash
            or user.email_verified_at is not None
        ):
            return

        now = datetime.now(UTC)
        self.db_session.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        ).update({"used_at": now}, synchronize_session=False)

        raw_token = self.new_email_verification_token()
        self.db_session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=self.hash_email_verification_token(raw_token),
                created_at=now,
                expires_at=now + timedelta(hours=_EMAIL_VERIFICATION_EXPIRES_HOURS),
                request_ip=ip,
                user_agent=user_agent,
            )
        )
        self.db_session.flush()
        self._deliver_email_verification_email(user.email, raw_token, user.id)

    def confirm_email_verification(self, token: str) -> None:
        token = token.strip()
        if not token:
            raise ValueError("Invalid or expired verification token.")

        token_hash = self.hash_email_verification_token(token)
        verification_token = (
            self.db_session.query(EmailVerificationToken)
            .filter_by(token_hash=token_hash)
            .one_or_none()
        )
        if (
            verification_token is None
            or verification_token.used_at is not None
            or self.is_expired(verification_token.expires_at)
        ):
            raise ValueError("Invalid or expired verification token.")

        user = self.db_session.get(User, verification_token.user_id)
        if (
            user is None
            or not user.is_active
            or user.role != "user"
            or user.auth_provider != "password"
            or not user.password_hash
        ):
            raise ValueError("Invalid or expired verification token.")

        now = datetime.now(UTC)
        if user.email_verified_at is None:
            user.email_verified_at = now
        verification_token.used_at = now
        self.db_session.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.id != verification_token.id,
        ).update({"used_at": now}, synchronize_session=False)
        self.db_session.flush()

    # -- email delivery ---------------------------------------------------------

    def _deliver_password_reset_email(self, email: str, token: str, user_id: int) -> None:
        if self.mailer is None:
            logger.info("Password reset email delivery skipped (no mailer configured) for user_id=%s.", user_id)
            return
        self.mailer.send_password_reset_email(email=email, token=token, user_id=user_id)

    def _deliver_email_verification_email(self, email: str, token: str, user_id: int) -> None:
        if self.mailer is None:
            logger.info("Email verification delivery skipped (no mailer configured) for user_id=%s.", user_id)
            return
        self.mailer.send_email_verification_email(email=email, token=token, user_id=user_id)

    # -- Google OAuth -----------------------------------------------------------

    def upsert_google_user(self, profile: GoogleOAuthProfile) -> User:
        if not profile.email_verified:
            raise ValueError("Google account email must be verified.")

        email = self.normalize_email(profile.email)
        if not email:
            raise ValueError("Google account email is missing.")

        user = (
            self.db_session.query(User)
            .filter_by(auth_provider="google", auth_provider_subject=profile.subject)
            .one_or_none()
        )
        email_user = (
            self.db_session.query(User)
            .filter(func.lower(User.email) == email)
            .one_or_none()
        )

        if user is None and email_user is not None:
            if email_user.role == "owner":
                raise ValueError("Public OAuth cannot link to the owner account.")
            if email_user.auth_provider and (
                email_user.auth_provider != "google"
                or email_user.auth_provider_subject != profile.subject
            ):
                raise ValueError("An account already exists for this email.")
            user = email_user
            user.auth_provider = "google"
            user.auth_provider_subject = profile.subject

        if user is not None:
            if user.role == "owner":
                raise ValueError("Public OAuth cannot authenticate the owner account.")
            if not user.is_active:
                raise ValueError("This account is inactive.")
            user.email = email
            if profile.display_name:
                user.display_name = profile.display_name
            if user.email_verified_at is None:
                user.email_verified_at = datetime.now(UTC)
            user.last_login_at = datetime.now(UTC)
            self.db_session.flush()
            return user

        user = User(
            email=email,
            display_name=profile.display_name,
            role="user",
            auth_provider="google",
            auth_provider_subject=profile.subject,
            email_verified_at=datetime.now(UTC),
            is_active=True,
            last_login_at=datetime.now(UTC),
        )
        self.db_session.add(user)
        self.db_session.flush()
        return user
