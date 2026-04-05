from __future__ import annotations

import hashlib
import json
import random
import re
import secrets
from dataclasses import dataclass

from .persistence.persistent_kv import PersistentKV

_ORDERING_NAMESPACE = "prompt_ordering"
_IMAGINE_SEED_KEY = "imagine_seed"
_URL_TOKEN = re.compile(r"^(?:<url>|<?https?://[^\s>]+>?)(?:::\S+)?$")
_URL_PAYLOAD_FLAGS = {"--sref", "--cref", "--oref", "--end"}


@dataclass(frozen=True)
class PromptImageChunk:
    urls: list[str]

    def render(self) -> str:
        return " ".join(self.urls).strip()


@dataclass(frozen=True)
class PromptFlagGroup:
    flag_name: str
    text: str

    def render(self) -> str:
        return self.text.strip()


@dataclass(frozen=True)
class ParsedPrompt:
    body: str
    user_flag_groups: list[PromptFlagGroup]


PromptUnit = PromptImageChunk | PromptFlagGroup


def derive_seed(seed: int, label: str) -> int:
    payload = f"{seed}:{label}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def load_or_create_imagine_seed(store: PersistentKV | None) -> int:
    if store is None:
        return 0
    raw = store.get(_ORDERING_NAMESPACE, _IMAGINE_SEED_KEY)
    if raw is not None:
        return int(json.loads(raw))
    seed = secrets.randbits(64)
    store.put(_ORDERING_NAMESPACE, _IMAGINE_SEED_KEY, json.dumps(seed))
    return seed


def parse_user_prompt(prompt: str | None) -> ParsedPrompt:
    tokens = _split_tokens(prompt)
    if not tokens:
        return ParsedPrompt(body="", user_flag_groups=[])
    first_flag = next((i for i, token in enumerate(tokens) if token.startswith("--")), None)
    if first_flag is None:
        return ParsedPrompt(body=" ".join(tokens).strip(), user_flag_groups=[])
    body = " ".join(tokens[:first_flag]).strip()
    flag_groups = _parse_flag_groups(tokens[first_flag:])
    return ParsedPrompt(body=body, user_flag_groups=flag_groups)


def build_flag_group(flag_name: str, *parts: str) -> PromptFlagGroup:
    text = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    normalized_name = flag_name.strip().lower()
    if not text:
        text = normalized_name
    return PromptFlagGroup(flag_name=normalized_name, text=text)


def order_imagine_prompt(
    *,
    prompt: str | None,
    prompt_image_urls: list[str],
    managed_groups: list[PromptFlagGroup],
    store: PersistentKV | None,
    seed_override: int | None = None,
) -> str:
    parsed = parse_user_prompt(prompt)
    seed = seed_override if seed_override is not None else load_or_create_imagine_seed(store)
    return serialize_prompt(
        body=parsed.body,
        ordered_no_groups=_extract_no_groups(parsed.user_flag_groups),
        movable_units=_order_units(
            parsed.user_flag_groups,
            prompt_image_urls=prompt_image_urls,
            managed_groups=managed_groups,
            seed=seed,
        ),
    )


def normalize_imagine_prompt_for_matching(prompt: str | None) -> str:
    tokens = _normalize_urls(_split_tokens(prompt))
    if not tokens:
        return ""
    first_suffix = next(
        (i for i, token in enumerate(tokens) if token.startswith("--") or _is_url_token(token)),
        None,
    )
    if first_suffix is None:
        return " ".join(tokens).strip()
    body = " ".join(tokens[:first_suffix]).strip()
    units = _parse_prompt_units(tokens[first_suffix:])
    no_groups = [
        unit for unit in units if isinstance(unit, PromptFlagGroup) and unit.flag_name == "--no"
    ]
    remainder = [unit for unit in units if unit not in no_groups]
    retained_groups = [
        unit.render()
        for unit in remainder
        if isinstance(unit, PromptFlagGroup)
        and unit.flag_name not in {"--sref", "--cref", "--oref"}
    ]
    retained_images = [unit.render() for unit in remainder if isinstance(unit, PromptImageChunk)]
    parts: list[str] = []
    if body:
        parts.append(body)
    parts.extend(group.render() for group in no_groups)
    parts.extend(retained_groups)
    if not parts:
        parts.extend(retained_images)
    return " ".join(part for part in parts if part).strip()


def serialize_prompt(
    *,
    body: str,
    ordered_no_groups: list[PromptFlagGroup],
    movable_units: list[PromptUnit],
) -> str:
    parts: list[str] = []
    if body:
        parts.append(body.strip())
    parts.extend(group.render() for group in ordered_no_groups)
    parts.extend(_render_unit(unit) for unit in movable_units)
    return " ".join(part for part in parts if part).strip()


def _extract_no_groups(groups: list[PromptFlagGroup]) -> list[PromptFlagGroup]:
    return [group for group in groups if group.flag_name == "--no"]


def _order_units(
    user_groups: list[PromptFlagGroup],
    *,
    prompt_image_urls: list[str],
    managed_groups: list[PromptFlagGroup],
    seed: int,
) -> list[PromptUnit]:
    movable: list[PromptUnit] = [group for group in user_groups if group.flag_name != "--no"]
    if prompt_image_urls:
        movable.append(PromptImageChunk(urls=list(prompt_image_urls)))
    movable.extend(managed_groups)
    rng = random.Random(derive_seed(seed, "suffix_units"))
    rng.shuffle(movable)
    return movable


def _split_tokens(prompt: str | None) -> list[str]:
    if not prompt:
        return []
    return prompt.strip().split()


def _parse_flag_groups(tokens: list[str]) -> list[PromptFlagGroup]:
    groups: list[PromptFlagGroup] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            index += 1
            continue
        end = index + 1
        while end < len(tokens) and not tokens[end].startswith("--"):
            end += 1
        group_tokens = tokens[index:end]
        groups.append(
            PromptFlagGroup(
                flag_name=group_tokens[0].lower(),
                text=" ".join(group_tokens).strip(),
            )
        )
        index = end
    return groups


def _normalize_urls(tokens: list[str]) -> list[str]:
    normalized: list[str] = []
    for token in tokens:
        if token.startswith("--"):
            normalized.append(token)
            continue
        if _URL_TOKEN.match(token):
            normalized.append("<url>")
            continue
        normalized.append(token)
    return normalized


def _parse_prompt_units(tokens: list[str]) -> list[PromptUnit]:
    units: list[PromptUnit] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            flag_name = token.lower()
            end = index + 1
            while end < len(tokens) and not tokens[end].startswith("--"):
                if _is_url_token(tokens[end]) and flag_name not in _URL_PAYLOAD_FLAGS:
                    break
                end += 1
            group_tokens = tokens[index:end]
            units.append(
                PromptFlagGroup(
                    flag_name=group_tokens[0].lower(), text=" ".join(group_tokens).strip()
                )
            )
            index = end
            continue
        if _is_url_token(token):
            end = index + 1
            while end < len(tokens) and _is_url_token(tokens[end]):
                end += 1
            units.append(PromptImageChunk(urls=list(tokens[index:end])))
            index = end
            continue
        index += 1
    return units


def _is_url_token(token: str) -> bool:
    return bool(_URL_TOKEN.match(token))


def _render_unit(unit: PromptUnit) -> str:
    return unit.render()


__all__ = [
    "ParsedPrompt",
    "PromptFlagGroup",
    "PromptImageChunk",
    "build_flag_group",
    "derive_seed",
    "load_or_create_imagine_seed",
    "normalize_imagine_prompt_for_matching",
    "order_imagine_prompt",
    "parse_user_prompt",
    "serialize_prompt",
]
