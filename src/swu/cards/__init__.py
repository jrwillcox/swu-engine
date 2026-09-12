"""Card ability registrations.

Importing this package (or any set submodule) registers every set's abilities as
a side effect, so the registry is fully populated regardless of entry point.
Add new sets here as they are encoded.
"""
import swu.cards.sor  # noqa: F401 — side-effect: registers SOR abilities
import swu.cards.shd  # noqa: F401 — side-effect: registers SHD abilities
import swu.cards.law  # noqa: F401 — side-effect: registers LAW abilities
import swu.cards.jtl  # noqa: F401 — side-effect: registers JTL abilities
import swu.cards.sec  # noqa: F401 — side-effect: registers SEC abilities
import swu.cards.twi  # noqa: F401 — side-effect: registers TWI abilities
import swu.cards.lof  # noqa: F401 — side-effect: registers LOF abilities
import swu.cards.ash  # noqa: F401 — side-effect: registers ASH abilities
import swu.cards.ibh  # noqa: F401 — side-effect: registers IBH abilities
import swu.cards.ts26  # noqa: F401 — side-effect: registers TS26 abilities
import swu.cards.promo  # noqa: F401 — side-effect: registers promo/anthology abilities

# LAST: after every set module has registered its abilities, alias reprint
# duplicates onto their implemented twins (a no-op while REPRINT_ALIASES is empty).
from swu.cards import reprints  # noqa: E402 — must import after all set modules load

reprints.apply_reprint_aliases()
