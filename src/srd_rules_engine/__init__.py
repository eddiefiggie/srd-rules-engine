"""SRD 5.2 rules engine.

The agent decides *that* a rule applies and *which* one. This library decides
*how it turns out*, and is the only thing that may.

See README.md for the architecture and NOTICE.md for attribution.
"""

# Date-based build stamp: mmddyyyy.x. `tests/test_build_stamp.py` fails the build
# when README.md's "Current build" line drifts from this value, so the README
# cannot silently go stale behind the code.
__version__ = "08252026.15"

__all__ = ["__version__"]
