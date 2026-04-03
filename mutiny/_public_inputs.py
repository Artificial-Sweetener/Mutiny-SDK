from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .public_models import ImageInput, VideoInput
from .services.image_utils import parse_data_url


def _is_remote_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _read_path_bytes(path: Path) -> bytes:
    if not path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")
    return path.read_bytes()


async def _read_remote_bytes_async(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _read_remote_bytes(url: str) -> bytes:
    with httpx.Client() as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def _guess_mime_from_name(name: str) -> str | None:
    mime_type, _encoding = mimetypes.guess_type(name)
    return mime_type


def _guess_mime_from_bytes(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    return None


def _guess_image_mime(value: ImageInput, image_bytes: bytes) -> str:
    if isinstance(value, Path):
        mime_type = _guess_mime_from_name(value.name)
        if mime_type:
            return mime_type
    elif isinstance(value, str):
        parsed = parse_data_url(value)
        if parsed is not None:
            return parsed.mime_type
        if _is_remote_url(value):
            remote_path = urlparse(value).path
            mime_type = _guess_mime_from_name(remote_path)
        else:
            mime_type = _guess_mime_from_name(value)
        if mime_type:
            return mime_type
    mime_type = _guess_mime_from_bytes(image_bytes)
    if mime_type:
        return mime_type
    raise ValueError("Unable to determine image MIME type from input")


async def read_binary_input_async(value: VideoInput) -> bytes:
    """Return raw bytes for a host-facing image or video input."""

    if isinstance(value, bytes):
        return value
    if isinstance(value, Path):
        return _read_path_bytes(value)
    parsed = parse_data_url(value)
    if parsed is not None:
        return parsed.data
    if _is_remote_url(value):
        return await _read_remote_bytes_async(value)
    return _read_path_bytes(Path(value))


def read_binary_input(value: VideoInput) -> bytes:
    """Return raw bytes for a host-facing image or video input."""

    if isinstance(value, bytes):
        return value
    if isinstance(value, Path):
        return _read_path_bytes(value)
    parsed = parse_data_url(value)
    if parsed is not None:
        return parsed.data
    if _is_remote_url(value):
        return _read_remote_bytes(value)
    return _read_path_bytes(Path(value))


def _data_url_from_bytes(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def normalize_image_input(value: ImageInput) -> str:
    """Normalize one host-facing image input to the data URL form used internally."""

    if isinstance(value, str):
        parsed = parse_data_url(value)
        if parsed is not None:
            return value
    image_bytes = await read_binary_input_async(value)
    mime_type = _guess_image_mime(value, image_bytes)
    return _data_url_from_bytes(image_bytes, mime_type)


async def normalize_image_inputs(values: tuple[ImageInput, ...]) -> tuple[str, ...]:
    """Normalize a batch of host-facing image inputs to data URLs."""

    normalized: list[str] = []
    for value in values:
        normalized.append(await normalize_image_input(value))
    return tuple(normalized)
