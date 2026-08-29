# Production composition root: core API + persistence/commerce + provider hardening + security/extensions.
from .bootstrap import app
from . import extensions as _extensions  # noqa: F401,E402

__all__ = ["app"]
