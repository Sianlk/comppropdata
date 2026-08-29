# Production composition root: core API + persistence/commerce + intelligence + private provider adapters + agents + secure documents + operational trust/readiness/security.
from .bootstrap import app
from . import extensions as _extensions  # noqa: F401,E402
from . import intelligence as _intelligence  # noqa: F401,E402
from . import provider_privacy as _provider_privacy  # noqa: F401,E402
from . import agents as _agents  # noqa: F401,E402
from . import documents as _documents  # noqa: F401,E402
from . import operations as _operations  # noqa: F401,E402
from . import readiness as _readiness  # noqa: F401,E402
from . import policy_security as _policy_security  # noqa: F401,E402

__all__ = ["app"]
