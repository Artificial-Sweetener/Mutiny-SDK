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

import logging

from mutiny.services.logging_utils import SensitiveDataFilter, clear_job_context, set_job_context


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord):  # type: ignore[override]
        msg = record.msg % record.args if record.args else str(record.msg)
        self.records.append(msg)


def test_log_correlation_prefix_added():
    logger = logging.getLogger("test.correlation")
    logger.setLevel(logging.INFO)
    handler = ListHandler()
    logger.addHandler(handler)
    # Install only the SensitiveDataFilter since it injects the correlation prefix
    logger.addFilter(SensitiveDataFilter())

    set_job_context(job_id="j1", action="IMAGINE", status="IN_PROGRESS", latency_ms=1250)
    try:
        logger.info("hello world")
    finally:
        clear_job_context()

    assert handler.records and handler.records[0].startswith(
        "[job_id=j1 action=IMAGINE status=IN_PROGRESS latency_ms=1250] "
    )
