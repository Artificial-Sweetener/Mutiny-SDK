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

import json

from mutiny.services.response_dump import ResponseDumpService


def test_dump_error_writes_error_summary(tmp_path):
    dump = ResponseDumpService(root_dir=str(tmp_path), enabled=True)
    message = {
        "id": "msg-1",
        "content": "",
        "embeds": [
            {
                "title": "Sorry, something went wrong",
                "description": "The job encountered an error. Our team has been notified.",
                "footer": {"text": "decline-revise-frolic"},
            }
        ],
        "message_reference": {"message_id": "progress-1"},
    }

    dump.dump_error(
        message=message,
        error_title="Sorry, something went wrong",
        error_description="The job encountered an error. Our team has been notified.",
        error_footer="decline-revise-frolic",
    )

    summary = json.loads((tmp_path / "index.jsonl").read_text(encoding="utf-8").strip())
    assert summary["kind"] == "ERROR"
    assert summary["message_id"] == "msg-1"
    assert summary["referenced_message_id"] == "progress-1"
    assert summary["error_footer"] == "decline-revise-frolic"
