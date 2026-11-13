"""`python -m studio.manim_cli render ...` == `manim render ...`, but imports
`studio` first so its sox stub is in place before Manim loads plugins."""

import studio  # noqa: F401  (side effects: sox stub, warning filters)
from manim.__main__ import main

if __name__ == "__main__":
    main()
