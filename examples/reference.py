#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Entry point for the Mutiny Reference GUI."""

from __future__ import annotations

import pathlib
import sys

if __package__ is None:
    # Allow running as `python examples/reference.py` by adding repo root to sys.path.
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from examples.reference.app import MutinyReferenceApp


def main() -> None:
    app = MutinyReferenceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
