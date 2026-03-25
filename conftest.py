"""Root-level conftest — loaded by pytest *before* ``tests/conftest.py``.

Sanitises ``sys.path`` **and** ``sys.modules`` so that site-packages
compiled for a different Python minor version (e.g. 3.13 in a Codegen
sandbox) never shadow packages inside the project's 3.12 venv.

Because pytest itself may import lightweight pure-Python packages
(e.g. ``typing_extensions``) from the contaminated path during its own
plugin loading — *before* any conftest is executed — we must also
evict those already-loaded modules so subsequent imports re-resolve
from the correct venv.

Safe no-op when no contamination is present.
"""

from bridge._pythonpath import sanitize_python_path

_removed = sanitize_python_path()
if _removed:
    import logging

    logging.getLogger("conftest").info(
        "Stripped %d foreign sys.path entries: %s",
        len(_removed),
        _removed,
    )
