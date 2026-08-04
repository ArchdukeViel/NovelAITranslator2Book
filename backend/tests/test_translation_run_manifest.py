from novelai.translation.run_manifest import TranslationRunManifest, is_translation_valid


def test_translation_run_manifest_dataclass():
    manifest = TranslationRunManifest(
        translation_run_id="run-1",
        novel_id="novel-1",
        prompt_version="v2",
        glossary_hash="g_hash123",
        provider_key="gemini",
        provider_model="gemini-1.5-pro",
    )
    assert manifest.translation_run_id == "run-1"
    assert manifest.glossary_hash == "g_hash123"

    d = manifest.to_dict()
    restored = TranslationRunManifest.from_dict(d)
    assert restored.translation_run_id == "run-1"
    assert restored.provider_model == "gemini-1.5-pro"


def test_is_translation_valid_returns_true_when_hashes_match():
    record = {
        "source_text_hash": "src_123",
        "glossary_hash": "g_123",
        "prompt_version": "v1",
        "provider_key": "gemini",
        "provider_model": "gemini-flash",
    }
    valid = is_translation_valid(
        source_text_hash="src_123",
        active_glossary_hash="g_123",
        prompt_version="v1",
        provider_key="gemini",
        provider_model="gemini-flash",
        record=record,
    )
    assert valid is True


def test_is_translation_valid_returns_false_when_source_hash_diverges():
    record = {
        "source_text_hash": "src_123",
        "glossary_hash": "g_123",
    }
    valid = is_translation_valid(
        source_text_hash="src_999",  # Modified text
        active_glossary_hash="g_123",
        prompt_version=None,
        provider_key=None,
        provider_model=None,
        record=record,
    )
    assert valid is False


def test_is_translation_valid_returns_false_when_glossary_hash_diverges():
    record = {
        "source_text_hash": "src_123",
        "glossary_hash": "g_old",
    }
    valid = is_translation_valid(
        source_text_hash="src_123",
        active_glossary_hash="g_new",  # Updated glossary
        prompt_version=None,
        provider_key=None,
        provider_model=None,
        record=record,
    )
    assert valid is False
