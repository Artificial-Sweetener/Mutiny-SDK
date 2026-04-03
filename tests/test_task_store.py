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

from mutiny.domain.job import Job, JobAction
from mutiny.services.job_store import InMemoryJobStoreService


def test_job_store_basic():
    store = InMemoryJobStoreService()
    t1 = Job(id="a", action=JobAction.IMAGINE)
    t2 = Job(id="b", action=JobAction.UPSCALE)

    store.save(t1)
    store.save(t2)

    assert store.get("a") is t1
    assert store.get("b") is t2
    ids = {t.id for t in store.list()}
    assert ids == {"a", "b"}
