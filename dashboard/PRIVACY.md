# Quantum Dashboard — privacy notes (read honestly)

**What this is:** a PIN-gated operational dashboard at an unguessable URL.
It shows bankroll, positions, discipline scores, and experiment verdicts —
MASTER INDY explicitly chose "show everything including bankroll."

**The PIN is a front-door lock, not a vault.**
- The gate compares the SHA-256 hash of the entered PIN against the hash in
  `config.json`. The plaintext PIN is never stored anywhere.
- `config.json` (hash only) ships in this public repo. A short numeric PIN
  could be brute-forced offline from that hash. The setup script therefore
  generates a 16-character alphanumeric PIN (~95 bits) by default — not
  brute-forceable with any realistic effort.
- There is no server-side rate limiting (static hosting). The real defenses
  are: (1) the unguessable 16-hex-char path, (2) `noindex, nofollow` so search
  engines ignore it, (3) the PIN itself.

**What NEVER ships in snapshot.json** (enforced in code, tested):
seed phrases, private keys, API keys/tokens, C-MGR formulas, model weights,
candidate internals, personal identifiers. The exporter builds the snapshot
from an explicit field allowlist, then runs a denylist scan that aborts the
export on any hit. See `cmgr/scripts/export_dashboard_snapshot.py`.

**Threat model, plainly:** this keeps casual visitors and crawlers out. It
does not stop a determined attacker who learns the URL — treat it like an
unlisted phone number with a good lock, not a bank vault. No secrets ever
live here, so there is nothing to steal beyond operational numbers.
