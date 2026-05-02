import pytest

from pocketStudio.core.ids import nanoid, prefixed_id


def test_nanoid_generates_url_safe_ids() -> None:
    value = nanoid(16)

    assert len(value) == 16
    assert all(ch.isalnum() or ch in "_-" for ch in value)
    assert value != nanoid(16)


def test_prefixed_id_normalizes_prefix() -> None:
    value = prefixed_id("My Project", size=8)

    assert value.startswith("my-project-")
    assert len(value.removeprefix("my-project-")) == 8


def test_nanoid_rejects_invalid_settings() -> None:
    with pytest.raises(ValueError):
        nanoid(0)
    with pytest.raises(ValueError):
        nanoid(4, alphabet="")
