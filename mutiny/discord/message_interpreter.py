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

"""Parses Discord gateway messages into structured Mutiny events.

Responsible for extracting prompts, statuses, hashes, and classification kinds
from Midjourney Discord messages while keeping raw payloads intact for freeze
tests and downstream consumers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import unquote, urlparse

from mutiny.discord.constants import ERROR_EMBED_COLOR

_IMAGINE_REGEX = re.compile(r"\*\*(?P<prompt>.*)\*\* - <@\d+> \((?P<status>.*?)\)", re.DOTALL)
_VARIATION_REGEX_1 = re.compile(
    r"\*\*(?P<prompt>.*)\*\* - Variations by <@\d+> \((?P<status>.*?)\)",
    re.DOTALL,
)
_VARIATION_REGEX_2 = re.compile(
    r"\*\*(?P<prompt>.*)\*\* - Variations \(.*?\) by <@\d+> \((?P<status>.*?)\)",
    re.DOTALL,
)
_REROLL_REGEX_1 = _IMAGINE_REGEX
_REROLL_REGEX_2 = _VARIATION_REGEX_1
_REROLL_REGEX_3 = _VARIATION_REGEX_2
_UPSCALE_REGEX_1 = re.compile(
    r"\*\*(?P<prompt>.*)\*\* - Upscaled \(.*?\) by <@\d+> \((?P<status>.*?)\)",
    re.DOTALL,
)
_UPSCALE_REGEX_2 = re.compile(
    r"\*\*(?P<prompt>.*)\*\* - Upscaled by <@\d+> \((?P<status>.*?)\)",
    re.DOTALL,
)
_UPSCALE_REGEX_3 = re.compile(r"\*\*(?P<prompt>.*)\*\* - Image #(?P<index>\d) <@\d+>", re.DOTALL)
_UPSCALE_REGEX_4 = re.compile(
    r"\*\*(?P<prompt>.*)\*\* - "
    r"(?P<kind>Zoom Out|Pan (?:Left|Right|Up|Down)|Animate \(High motion\)|Animate \(Low motion\)) "
    r"by <@\d+> \((?P<status>.*?)\)",
    re.DOTALL,
)
_UPSCALE_REGEX_5 = re.compile(
    r"\*\*(?P<prompt>.*)\*\* - <@\d+> .*?\((?:<)?https://midjourney\.com/jobs/[^)]+(?:>)?\) "
    r"\((?P<status>.*?)\)",
    re.DOTALL,
)
_PROGRESS_REGEX = re.compile(
    r".*?\*\*(?P<prompt>.*)\*\*.*<@\d+> \((?P<status>.*?)\)",
    re.DOTALL,
)
_UUID_HASH_REGEX = re.compile(
    r"(?P<message_hash>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_UNRECOGNIZED_PARAMETER_RE = re.compile(
    r"(?im)^unrecognized parameter\(s\)\s*:\s*(?P<detail>.+?)\s*$"
)


class MessageKind(str, Enum):
    PROGRESS = "progress"
    DESCRIBE_START = "describe_start"
    DESCRIBE_DONE = "describe_done"
    ERROR = "error"
    GENERIC_SUCCESS = "generic_success"
    VARIATION_SUCCESS = "variation_success"
    UPSCALE_SUCCESS = "upscale_success"
    BLEND_SUCCESS = "blend_success"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProgressParse:
    """Minimal progress view exposing prompt and textual status when available."""

    prompt: Optional[str]
    status: Optional[str]


@dataclass(frozen=True)
class InterpretedMessage:
    """Normalized Discord message snapshot with parsed kinds and preserved raw payload."""

    event_type: str
    kinds: frozenset[MessageKind]
    message_id: Optional[str]
    content: str
    prompt: Optional[str]
    status: Optional[str]
    interaction_id: Optional[str]
    interaction_name: Optional[str]
    nonce: Optional[str]
    referenced_message_id: Optional[str]
    image_url: Optional[str]
    message_hash: Optional[str]
    upscale_variant: Optional[str]
    flags: Optional[int]
    embeds: list[dict]
    components: list[dict]
    attachments: list[dict]
    error_title: Optional[str]
    error_description: Optional[str]
    error_footer: Optional[str]
    raw: dict

    def has_kind(self, kind: MessageKind) -> bool:
        return kind in self.kinds

    def as_progress(self) -> Optional[ProgressParse]:
        if not self.has_kind(MessageKind.PROGRESS):
            return None
        return ProgressParse(prompt=self.prompt, status=self.status)


class DiscordMessageParser:
    """Parse Discord gateway events into typed message interpretations without mutation."""

    def interpret(self, event_type: str, message: dict) -> Optional[InterpretedMessage]:
        """Classify a Discord gateway message and extract prompt, status, and metadata.

        Args:
            event_type: Gateway dispatch name associated with the message (e.g., MESSAGE_CREATE).
            message: Raw Discord message payload.

        Returns:
                        A frozen `InterpretedMessage` describing detected kinds, prompt/status text,
                        hash, embeds, components, attachments, and the preserved raw payload.
                        Returns ``None`` when the payload is not a mapping.

        Notes:
                        - Kind detection is order-aware: progress first, then
                            generic/variation/upscale successes; absence yields UNKNOWN.
                        - Error classification uses a narrow Midjourney-specific embed helper and
                            still requires a referenced message id to avoid false positives.
                        - Regex definitions are behavior-frozen; do not alter pattern shapes without
                            updating downstream freeze tests.
        """
        if not isinstance(message, dict):
            return None
        content = message.get("content") or ""
        message_id = message.get("id")
        flags = message.get("flags")
        flags_value = int(flags) if flags is not None else None
        interaction = message.get("interaction") or {}
        interaction_id = interaction.get("id")
        interaction_name = interaction.get("name")
        nonce = message.get("nonce")
        referenced_message_id = (message.get("message_reference") or {}).get("message_id")
        embeds = message.get("embeds") or []
        components = message.get("components") or []
        attachments = message.get("attachments") or []
        image_url = attachments[0].get("url") if attachments else None
        message_hash = extract_message_hash(image_url) if image_url else None
        upscale_variant = None

        kinds: set[MessageKind] = set()
        prompt = None
        status = None
        error_title = None
        error_description = None
        error_footer = None

        if interaction_name == "describe" and nonce:
            kinds.add(MessageKind.DESCRIBE_START)

        if embeds:
            embed = embeds[0] or {}
            if _is_midjourney_error_embed(embed, referenced_message_id):
                kinds.add(MessageKind.ERROR)
                error_title = embed.get("title") or ""
                error_description = embed.get("description") or ""
                error_footer = ((embed.get("footer") or {}).get("text") or "").strip() or None
            elif embed.get("description") is not None:
                kinds.add(MessageKind.DESCRIBE_DONE)
                prompt = embed.get("description") or ""
                image = embed.get("image") or {}
                if image.get("url"):
                    image_url = image.get("url")

        if (
            referenced_message_id
            and not kinds.intersection({MessageKind.ERROR, MessageKind.DESCRIBE_DONE})
            and _is_midjourney_error_content(content)
        ):
            kinds.add(MessageKind.ERROR)
            error_title, error_description = _parse_midjourney_error_content(content)

        progress_match = _PROGRESS_REGEX.match(content)
        if progress_match:
            kinds.add(MessageKind.PROGRESS)
            prompt = prompt or progress_match.group("prompt")
            status = progress_match.group("status")

        generic_prompt = _match_prompt(
            content, (_IMAGINE_REGEX, _REROLL_REGEX_1, _REROLL_REGEX_2, _REROLL_REGEX_3)
        )
        if generic_prompt:
            kinds.add(MessageKind.GENERIC_SUCCESS)
            prompt = prompt or generic_prompt
            if generic_prompt.startswith("<https://s.mj.run"):
                kinds.add(MessageKind.BLEND_SUCCESS)

        variation_prompt = _match_prompt(content, (_VARIATION_REGEX_1, _VARIATION_REGEX_2))
        if variation_prompt:
            kinds.add(MessageKind.VARIATION_SUCCESS)
            prompt = prompt or variation_prompt

        upscale_prompt, upscale_variant = _match_upscale(content)
        if upscale_prompt:
            kinds.add(MessageKind.UPSCALE_SUCCESS)
            prompt = prompt or upscale_prompt

        if not kinds:
            kinds.add(MessageKind.UNKNOWN)

        return InterpretedMessage(
            event_type=event_type,
            kinds=frozenset(kinds),
            message_id=message_id,
            content=content,
            prompt=prompt,
            status=status,
            interaction_id=interaction_id,
            interaction_name=interaction_name,
            nonce=nonce,
            referenced_message_id=referenced_message_id,
            image_url=image_url,
            message_hash=message_hash,
            upscale_variant=upscale_variant,
            flags=flags_value,
            embeds=embeds,
            components=components,
            attachments=attachments,
            error_title=error_title,
            error_description=error_description,
            error_footer=error_footer,
            raw=message,
        )


def _match_prompt(content: str, patterns: tuple[re.Pattern[str], ...]) -> Optional[str]:
    """Return the first prompt captured by the provided patterns or ``None``.

    Patterns are evaluated in order to preserve Midjourney parsing precedence; content is treated
    as-is to keep freeze tests stable.
    """
    for regex in patterns:
        match = regex.match(content or "")
        if match:
            return match.group("prompt")
    return None


def _match_upscale(content: str) -> tuple[Optional[str], Optional[str]]:
    """Return one parsed upscale prompt plus a normalized variant label."""

    match = _UPSCALE_REGEX_4.match(content or "")
    if match:
        kind = (match.group("kind") or "").strip().lower()
        if kind == "zoom out":
            return match.group("prompt"), "zoom_out"
        if kind.startswith("pan "):
            return match.group("prompt"), kind.replace(" ", "_")
        if kind == "animate (high motion)":
            return match.group("prompt"), "animate_high"
        if kind == "animate (low motion)":
            return match.group("prompt"), "animate_low"
        return match.group("prompt"), "upscaled"

    match = _UPSCALE_REGEX_3.match(content or "")
    if match:
        return match.group("prompt"), "tile_promotion"

    prompt = _match_prompt(content, (_UPSCALE_REGEX_1, _UPSCALE_REGEX_2, _UPSCALE_REGEX_5))
    if prompt:
        return prompt, "upscaled"
    return None, None


def _is_midjourney_error_embed(embed: dict, referenced_message_id: Optional[str]) -> bool:
    """Return whether an embed is a Midjourney job failure reply.

    Midjourney sometimes omits the historical error color from decline/error
    embeds while still sending a referenced reply with stable title,
    description, or footer text. Keep this helper narrow by requiring a
    referenced message id and matching only known failure markers.
    """
    if not referenced_message_id:
        return False

    title = str(embed.get("title") or "").strip().lower()
    description = str(embed.get("description") or "").strip().lower()
    footer = embed.get("footer") or {}
    footer_text = str(footer.get("text") or "").strip().lower()

    return (
        embed.get("color") == ERROR_EMBED_COLOR
        or title == "slow down!"
        or title == "sorry, something went wrong"
        or "the job encountered an error" in description
        or footer_text.startswith("decline-")
    )


def _is_midjourney_error_content(content: str) -> bool:
    """Return whether one referenced message body matches Midjourney validation failures."""

    normalized = str(content or "").strip().lower()
    return bool(
        normalized.startswith("invalid parameter")
        or _UNRECOGNIZED_PARAMETER_RE.search(content or "")
    )


def _parse_midjourney_error_content(content: str) -> tuple[str | None, str | None]:
    """Extract a compact title/description pair from one Midjourney error body."""

    lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
    if not lines:
        return None, None

    title = lines[0]
    parameter_match = _UNRECOGNIZED_PARAMETER_RE.search(content or "")
    if parameter_match is not None:
        return title, f"Unrecognized parameter(s): {parameter_match.group('detail').strip()}"

    if len(lines) > 1:
        return title, lines[1]

    return title, None


def extract_message_hash(attachment_ref: Optional[str]) -> Optional[str]:
    """Derive the Midjourney message hash from one attachment URL or filename.

    Midjourney uses multiple attachment naming schemes across images, prompt-video
    previews, and final mp4 replies. Prefer extracting a UUID-style job hash when
    one is embedded anywhere in the filename stem, while preserving the historical
    image-grid fallback behavior.
    """
    if not attachment_ref:
        return None
    parsed = urlparse(attachment_ref)
    filename = unquote((parsed.path or attachment_ref).rsplit("/", maxsplit=1)[-1])
    stem = filename.rsplit(".", maxsplit=1)[0]
    if "_grid_0.webp" in filename:
        return filename.replace("_grid_0.webp", "")
    uuid_match = _UUID_HASH_REGEX.search(stem)
    if uuid_match is not None:
        return uuid_match.group("message_hash")
    return stem.split("_")[-1]


__all__ = [
    "DiscordMessageParser",
    "InterpretedMessage",
    "MessageKind",
    "ProgressParse",
    "extract_message_hash",
]
