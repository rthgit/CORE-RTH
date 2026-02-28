"""
Poll mailbox once and print results.

Required env vars:
- RTH_IMAP_HOST
- RTH_IMAP_PORT (default 993)
- RTH_IMAP_USER
- RTH_IMAP_PASSWORD
- RTH_IMAP_FOLDER (default INBOX)
- RTH_MAIL_SHARED_SECRET

Optional:
- RTH_MAIL_ALLOWED_SENDERS (comma separated)
- RTH_MAIL_ALLOW_APPROVE=1
- RTH_MAIL_MAX_RISK=low|medium|high
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.jarvis import jarvis_core


def main() -> int:
    out = jarvis_core.mail_poll_once(limit=20)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

