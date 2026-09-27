"""The rules a committed day has to pass, one module each.

A module here declares `CHECK` (or a `CHECKS` tuple) and nothing else is
required of it. `idhazh.publication_checks.registry` finds it by walking this
package, so adding a rule is adding a file - no list to join, no import to
remember.
"""

from __future__ import annotations
