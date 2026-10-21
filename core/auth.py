from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
from pathlib import Path
from secrets import token_bytes, token_urlsafe
import base64
import json
import sqlite3
from uuid import uuid4


ALLOWED_ROLES = {"enterprise", "seeker"}
SESSION_DAYS = 7
PASSWORD_ITERATIONS = 240_000


class AuthError(ValueError):
    pass


class AuthService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._seed_first_run_accounts()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    organization_id TEXT,
                    organization_name TEXT,
                    profile TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    application_id TEXT PRIMARY KEY,
                    seeker_user_id TEXT NOT NULL,
                    organization_id TEXT,
                    job_id TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    source_url TEXT,
                    status TEXT NOT NULL,
                    match_score INTEGER,
                    snapshot TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(seeker_user_id, job_id)
                )
                """
            )

    def _seed_first_run_accounts(self) -> None:
        self._seed_user(
            email="hr@talentgraph.cn",
            password="talentgraph2026",
            role="enterprise",
            display_name="企业招聘团队",
            organization_id="org_nebula",
            organization_name="星云科技",
        )
        self._seed_user(
            email="candidate@talentgraph.cn",
            password="talentgraph2026",
            role="seeker",
            display_name="求职者",
        )

    def _seed_user(
        self,
        *,
        email: str,
        password: str,
        role: str,
        display_name: str,
        organization_id: str | None = None,
        organization_name: str | None = None,
    ) -> None:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.casefold(),),
            ).fetchone()
            if exists:
                return
            now = datetime.now(UTC).isoformat()
            connection.execute(
                """
                INSERT INTO users (
                    user_id, email, password_hash, role, display_name,
                    organization_id, organization_name, profile, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"user_{uuid4().hex[:12]}",
                    email.casefold(),
                    self._hash_password(password),
                    role,
                    display_name,
                    organization_id,
                    organization_name,
                    "{}",
                    now,
                    now,
                ),
            )

    def register(
        self,
        *,
        email: str,
        password: str,
        role: str,
        display_name: str,
        organization_name: str | None = None,
    ) -> dict:
        normalized_email = email.strip().casefold()
        if role not in ALLOWED_ROLES:
            raise AuthError("不支持的用户角色")
        if len(password) < 8:
            raise AuthError("密码至少需要 8 个字符")
        if not normalized_email or "@" not in normalized_email:
            raise AuthError("请输入有效邮箱")
        organization_id = f"org_{uuid4().hex[:10]}" if role == "enterprise" else None
        now = datetime.now(UTC).isoformat()
        user_id = f"user_{uuid4().hex[:12]}"
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id, email, password_hash, role, display_name,
                        organization_id, organization_name, profile, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        normalized_email,
                        self._hash_password(password),
                        role,
                        display_name.strip() or normalized_email.split("@", 1)[0],
                        organization_id,
                        organization_name.strip() if organization_name else None,
                        "{}",
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise AuthError("该邮箱已经注册") from exc
        return self.get_user(user_id)

    def login(self, *, email: str, password: str, role: str | None = None) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.strip().casefold(),),
            ).fetchone()
        if not row or not self._verify_password(password, row["password_hash"]):
            raise AuthError("邮箱或密码错误")
        if role and row["role"] != role:
            raise AuthError("该账号不属于当前登录入口")
        user = self._serialize_user(row)
        raw_token = token_urlsafe(40)
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=SESSION_DAYS)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            connection.execute(
                "INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (self._token_hash(raw_token), user["user_id"], expires_at.isoformat(), now.isoformat()),
            )
        return {
            "access_token": raw_token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "user": user,
        }

    def resolve_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.*
                FROM auth_sessions
                JOIN users ON users.user_id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?
                """,
                (self._token_hash(token), now),
            ).fetchone()
        return self._serialize_user(row) if row else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE token_hash = ?",
                (self._token_hash(token),),
            )

    def get_user(self, user_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            raise AuthError("用户不存在")
        return self._serialize_user(row)

    def list_applications(self, user: dict) -> list[dict]:
        query = "SELECT * FROM applications"
        params: tuple = ()
        if user["role"] == "seeker":
            query += " WHERE seeker_user_id = ?"
            params = (user["user_id"],)
        elif user.get("organization_id"):
            query += " WHERE organization_id = ? OR organization_id IS NULL"
            params = (user["organization_id"],)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._serialize_application(row) for row in rows]

    def create_application(
        self,
        *,
        user: dict,
        job_id: str,
        job_title: str,
        company: str,
        source_url: str | None,
        match_score: int | None,
        snapshot: dict | None = None,
        organization_id: str | None = None,
    ) -> dict:
        if user["role"] != "seeker":
            raise AuthError("只有求职者可以投递简历")
        now = datetime.now(UTC).isoformat()
        application_id = f"application_{uuid4().hex[:12]}"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM applications WHERE seeker_user_id = ? AND job_id = ?",
                (user["user_id"], job_id),
            ).fetchone()
            if existing:
                return self._serialize_application(existing)
            connection.execute(
                """
                INSERT INTO applications (
                    application_id, seeker_user_id, organization_id, job_id,
                    job_title, company, source_url, status, match_score,
                    snapshot, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    user["user_id"],
                    organization_id,
                    job_id,
                    job_title,
                    company,
                    source_url,
                    "submitted",
                    match_score,
                    json.dumps(snapshot or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM applications WHERE application_id = ?",
                (application_id,),
            ).fetchone()
        return self._serialize_application(row)

    def update_application(self, application_id: str, status: str, user: dict) -> dict:
        allowed = {"submitted", "viewed", "interview", "offer", "rejected", "withdrawn"}
        if status not in allowed:
            raise AuthError("不支持的投递状态")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE application_id = ?",
                (application_id,),
            ).fetchone()
            if not row:
                raise AuthError("投递记录不存在")
            if user["role"] == "seeker":
                if row["seeker_user_id"] != user["user_id"] or status != "withdrawn":
                    raise AuthError("无权修改该投递记录")
            elif user.get("organization_id") and row["organization_id"] not in {None, user["organization_id"]}:
                raise AuthError("无权修改其他企业的投递记录")
            now = datetime.now(UTC).isoformat()
            connection.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE application_id = ?",
                (status, now, application_id),
            )
            updated = connection.execute(
                "SELECT * FROM applications WHERE application_id = ?",
                (application_id,),
            ).fetchone()
        return self._serialize_application(updated)

    @staticmethod
    def _serialize_user(row: sqlite3.Row) -> dict:
        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "role": row["role"],
            "display_name": row["display_name"],
            "organization_id": row["organization_id"],
            "organization_name": row["organization_name"],
            "profile": json.loads(row["profile"] or "{}"),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _serialize_application(row: sqlite3.Row) -> dict:
        return {
            "application_id": row["application_id"],
            "seeker_user_id": row["seeker_user_id"],
            "organization_id": row["organization_id"],
            "job_id": row["job_id"],
            "job_title": row["job_title"],
            "company": row["company"],
            "source_url": row["source_url"],
            "status": row["status"],
            "match_score": row["match_score"],
            "snapshot": json.loads(row["snapshot"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _token_hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = token_bytes(16)
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
        return "$".join(
            (
                "pbkdf2_sha256",
                str(PASSWORD_ITERATIONS),
                base64.urlsafe_b64encode(salt).decode("ascii"),
                base64.urlsafe_b64encode(digest).decode("ascii"),
            )
        )

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt_value, digest_value = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
            expected = base64.urlsafe_b64decode(digest_value.encode("ascii"))
            actual = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
            return compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
