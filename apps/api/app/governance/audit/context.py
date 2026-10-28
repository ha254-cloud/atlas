from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRequestContext:
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    device: str | None = None


_context: ContextVar[AuditRequestContext | None] = ContextVar("audit_request_context", default=None)


def current_audit_context() -> AuditRequestContext:
    return _context.get() or AuditRequestContext()


def set_audit_context(context: AuditRequestContext) -> Token:
    return _context.set(context)


def reset_audit_context(token: Token) -> None:
    _context.reset(token)


def classify_device(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    lowered = user_agent.lower()
    if any(marker in lowered for marker in ("mobile", "android", "iphone", "ipad")):
        return "mobile"
    return "desktop"
