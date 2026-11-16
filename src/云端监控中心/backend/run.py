from __future__ import annotations

import uvicorn

from app.core.settings import BIND_HOST, BIND_PORT, TRUSTED_PROXY


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=BIND_HOST,
        port=BIND_PORT,
        proxy_headers=bool(TRUSTED_PROXY),
        forwarded_allow_ips=TRUSTED_PROXY or None,
    )
