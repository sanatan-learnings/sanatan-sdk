"""Tests for collection overview image auto-generation trigger logic."""

from verse_sdk.cli.generate import should_auto_generate_collection_overview_images


def test_overview_images_auto_generated_when_first_verse_included():
    assert should_auto_generate_collection_overview_images([1]) is True
    assert should_auto_generate_collection_overview_images([1, 2, 3]) is True
    assert should_auto_generate_collection_overview_images([3, 1]) is True


def test_overview_images_not_auto_generated_for_non_first_verse_runs():
    assert should_auto_generate_collection_overview_images([2]) is False
    assert should_auto_generate_collection_overview_images([5, 6]) is False
    assert should_auto_generate_collection_overview_images([]) is False


def test_overview_images_can_be_forced_explicitly():
    assert should_auto_generate_collection_overview_images([7], explicit=True) is True
    assert should_auto_generate_collection_overview_images([], explicit=True) is True
