# Production composition root: core API + persistence/commerce + provider hardening + intelligence, agents, secure documents and policy/security extensions.
from .bootstrap import app
from . import extensions as _extensions  # noqa: F401,E402
from . import intelligence as _intelligence  # noqa: F401,E402
from . import agents as _agents  # noqa: F401,E402
from . import documents as _documents  # noqa: F401,E402
from . import policy_security as _policy_security  # noqa: F401,E402

__all__ = ["app"]
