from __future__ import annotations

from pathlib import Path

from mutiny.services.persistence.persistent_kv import PersistentKV
from mutiny.services.prompt_ordering import (
    build_flag_group,
    load_or_create_imagine_seed,
    normalize_imagine_prompt_for_matching,
    order_imagine_prompt,
    parse_user_prompt,
)


def _store(tmp_path: Path) -> PersistentKV:
    return PersistentKV(str(tmp_path / "kv.sqlite"))


def test_parse_user_prompt_splits_body_and_atomic_flag_groups():
    parsed = parse_user_prompt("cinematic portrait --v 4 --foo bar baz --no hat")

    assert parsed.body == "cinematic portrait"
    assert [group.text for group in parsed.user_flag_groups] == [
        "--v 4",
        "--foo bar baz",
        "--no hat",
    ]


def test_load_or_create_imagine_seed_persists_value(tmp_path):
    store = _store(tmp_path)
    first = load_or_create_imagine_seed(store)
    second = load_or_create_imagine_seed(store)

    assert first == second
    assert first >= 0
    store.close()


def test_order_imagine_prompt_keeps_no_second_and_groups_atomic():
    prompt = "cinematic portrait --v 4 --stylize 200 --no hat"

    result = order_imagine_prompt(
        prompt=prompt,
        prompt_image_urls=["https://cdn.example/prompt-a.png", "https://cdn.example/prompt-b.png"],
        managed_groups=[
            build_flag_group("--sref", "--sref https://cdn.example/style-a.png"),
            build_flag_group("--cref", "--cref https://cdn.example/character.png"),
        ],
        store=None,
        seed_override=7,
    )

    assert result.startswith("cinematic portrait --no hat ")
    assert " --v 4 " in f" {result} "
    assert " --stylize 200" in result
    assert "https://cdn.example/prompt-a.png https://cdn.example/prompt-b.png" in result
    assert "--sref https://cdn.example/style-a.png" in result
    assert "--cref https://cdn.example/character.png" in result


def test_order_imagine_prompt_is_deterministic_for_same_seed():
    kwargs = {
        "prompt": "body --ar 3:4 --stylize 200",
        "prompt_image_urls": ["https://cdn.example/prompt.png"],
        "managed_groups": [
            build_flag_group("--sref", "--sref https://cdn.example/style.png"),
            build_flag_group("--cref", "--cref https://cdn.example/character.png"),
            build_flag_group("--oref", "--oref https://cdn.example/omni.png"),
        ],
        "store": None,
    }

    first = order_imagine_prompt(**kwargs, seed_override=9)
    second = order_imagine_prompt(**kwargs, seed_override=9)

    assert first == second


def test_order_imagine_prompt_changes_group_order_for_different_seeds():
    kwargs = {
        "prompt": "body --ar 3:4 --stylize 200",
        "prompt_image_urls": ["https://cdn.example/prompt.png"],
        "managed_groups": [
            build_flag_group("--sref", "--sref https://cdn.example/style.png"),
            build_flag_group("--cref", "--cref https://cdn.example/character.png"),
        ],
        "store": None,
    }

    first = order_imagine_prompt(**kwargs, seed_override=1)
    second = order_imagine_prompt(**kwargs, seed_override=2)

    assert first != second


def test_normalize_imagine_prompt_for_matching_ignores_group_order():
    left = (
        "cinematic portrait --no hat https://cdn.example/prompt-a.png "
        "https://cdn.example/prompt-b.png --ar 3:4 --sref https://cdn.example/style.png"
    )
    right = (
        "cinematic portrait --no hat --sref https://cdn.example/style.png "
        "--ar 3:4 https://cdn.example/prompt-a.png https://cdn.example/prompt-b.png"
    )

    assert normalize_imagine_prompt_for_matching(left) == normalize_imagine_prompt_for_matching(
        right
    )
