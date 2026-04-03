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

from __future__ import annotations

from typing import Protocol


class GenerativeCommands(Protocol):
    """Protocol for Discord/Midjourney command operations."""

    async def send_button_interaction(
        self, message_id: str, custom_id: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def imagine(self, prompt: str, nonce: str) -> str | None: ...

    async def upscale(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def variation(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def reroll(
        self, message_id: str, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def vary_subtle(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def vary_strong(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def upscale_v7_subtle(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def upscale_v7_creative(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def outpaint_50(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def outpaint_75(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def pan_left(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def pan_right(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def pan_up(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def pan_down(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def animate_high(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def animate_low(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def animate_extend_high(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def animate_extend_low(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def custom_zoom(
        self, message_id: str, message_hash: str, message_flags: int, nonce: str, zoom_text: str
    ) -> str | None: ...

    async def inpaint_button(
        self, message_id: str, index: int, message_hash: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def inpaint_submit_job(
        self,
        *,
        iframe_token: str,
        mask_webp_base64: str,
        prompt: str | None,
    ) -> str | None: ...

    async def upload(self, filename: str, file_content: bytes, mime_type: str) -> str | None: ...

    async def send_image_message(
        self, content: str | None, uploaded_filename: str
    ) -> str | None: ...

    async def describe(self, uploaded_filename: str, nonce: str) -> str | None: ...

    async def describe_by_url(self, image_url: str, nonce: str) -> str | None: ...

    async def blend(
        self, uploaded_filenames: list[str], dimensions: str, nonce: str
    ) -> str | None: ...

    async def cancel_job(
        self, message_id: str, job_id: str, message_flags: int, nonce: str
    ) -> str | None: ...

    async def fetch_cdn_bytes(self, url: str) -> bytes | None: ...


__all__ = ["GenerativeCommands"]
