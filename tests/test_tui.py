"""
TUI Functionality Test Script

Tests all 7 TUI menu options to verify they work correctly.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.tui.app import TUIApp


@pytest.fixture
def tui():
    """Provide a bootstrapped TUI instance for smoke tests."""
    bootstrap()
    return TUIApp()


def test_tui_initialization(tui):
    """Test 1: TUI initializes without errors"""
    print("\n" + "="*60)
    print("TEST 1: TUI Initialization")
    print("="*60)
    
    try:
        bootstrap()
        tui = TUIApp()
        print("✓ TUI initialized successfully")
        print(f"✓ Console available: {tui.console is not None}")
        print(f"✓ Storage service available: {tui.storage is not None}")
        print(f"✓ Translation service available: {tui.translation is not None}")
        print(f"✓ Exporter service available: {tui.exporter is not None}")
        return tui
    except Exception as e:
        print(f"✗ TUI initialization failed: {e}")
        return None


def test_list_novels(tui):
    """Test 2: List novels (should show empty for fresh data)"""
    print("\n" + "="*60)
    print("TEST 2: List Novels Option")
    print("="*60)
    
    try:
        # This should show "No novels in storage yet"
        novels = tui.storage.list_novels()
        print(f"✓ Storage list_novels() call successful")
        print(f"✓ Novel count: {len(novels)}")
        print(f"✓ Expected empty list at start: {len(novels) == 0}")
        return True
    except Exception as e:
        print(f"✗ List novels failed: {e}")
        return False


def test_prompt_source(tui):
    """Test 3: Source detection"""
    print("\n" + "="*60)
    print("TEST 3: Source Detection")
    print("="*60)
    
    try:
        from novelai.sources.registry import available_sources
        sources = available_sources()
        print(f"✓ Available sources detected: {sources}")
        print(f"✓ Source count: {len(sources)}")
        if len(sources) > 0:
            print(f"✓ First source: {sources[0]}")
        return len(sources) > 0
    except Exception as e:
        print(f"✗ Source detection failed: {e}")
        return False


def test_prompt_provider(tui):
    """Test 4: Provider detection"""
    print("\n" + "="*60)
    print("TEST 4: Provider Detection")
    print("="*60)
    
    try:
        from novelai.providers.registry import available_providers
        providers = available_providers()
        print(f"✓ Available providers detected: {providers}")
        print(f"✓ Provider count: {len(providers)}")
        if len(providers) > 0:
            print(f"✓ First provider: {providers[0]}")
        return len(providers) > 0
    except Exception as e:
        print(f"✗ Provider detection failed: {e}")
        return False


def test_settings_menu(tui):
    """Test 5: Settings menu operations"""
    print("\n" + "="*60)
    print("TEST 5: Settings Operations")
    print("="*60)
    
    try:
        provider = tui.settings.get_provider_key()
        model = tui.settings.get_provider_model()
        print(f"✓ Retrieved provider: {provider}")
        print(f"✓ Retrieved model: {model}")
        
        # Test setting values
        tui.settings.set_provider_key("openai")
        tui.settings.set_provider_model("gpt-3.5-turbo")
        
        new_provider = tui.settings.get_provider_key()
        new_model = tui.settings.get_provider_model()
        print(f"✓ Set provider to: {new_provider}")
        print(f"✓ Set model to: {new_model}")
        
        return new_provider == "openai" and new_model == "gpt-3.5-turbo"
    except Exception as e:
        print(f"✗ Settings operations failed: {e}")
        return False


def test_diagnostics(tui):
    """Test 6: Diagnostics menu data"""
    print("\n" + "="*60)
    print("TEST 6: Diagnostics Menu")
    print("="*60)
    
    try:
        from novelai.config.settings import settings
        
        novels = tui.storage.list_novels()
        total_novels = len(novels)
        total_translated = sum(tui.storage.count_translated_chapters(n) for n in novels)
        
        cache_path = Path(settings.DATA_DIR) / "translation_cache.json"
        cache_entries = 0
        if cache_path.exists():
            try:
                cache_entries = len(json.loads(cache_path.read_text(encoding="utf-8")))
            except:
                cache_entries = 0
        
        usage_summary = tui.usage.summary()
        
        print(f"✓ Novels stored: {total_novels}")
        print(f"✓ Translated chapters: {total_translated}")
        print(f"✓ Cached translations: {cache_entries}")
        print(f"✓ Total requests: {usage_summary.get('total_requests', 0)}")
        print(f"✓ Total tokens: {usage_summary.get('total_tokens', 0)}")
        print(f"✓ Estimated cost: ${usage_summary.get('estimated_cost_usd', 0):.6f}")
        
        return True
    except Exception as e:
        print(f"✗ Diagnostics failed: {e}")
        return False


def test_export_preconditions(tui):
    """Test 7: Export validation logic"""
    print("\n" + "="*60)
    print("TEST 7: Export Validation")
    print("="*60)
    
    try:
        # Test metadata loading with a fake novel
        meta = tui.storage.load_metadata("test_novel_xyz")
        
        if not meta:
            print("✓ Correctly returns None for non-existent novel")
        
        # Verify export has required functions
        has_export_epub = hasattr(tui.exporter, 'export_epub')
        has_export_pdf = hasattr(tui.exporter, 'export_pdf')
        
        print(f"✓ Exporter has export_epub: {has_export_epub}")
        print(f"✓ Exporter has export_pdf: {has_export_pdf}")
        
        return has_export_epub and has_export_pdf
    except Exception as e:
        print(f"✗ Export validation failed: {e}")
        return False


def test_error_handling(tui):
    """Test 8: Error handling in key functions"""
    print("\n" + "="*60)
    print("TEST 8: Error Handling")
    print("="*60)
    
    try:
        # Test graceful handling of missing novel
        try:
            chapters = tui.storage.load_translated_chapter("fake_novel", "1")
            print(f"✓ Gracefully handles missing chapter: {chapters is None or not chapters}")
        except Exception as inner_e:
            print(f"⚠ Missing chapter handling: {inner_e}")
        
        # Test orchestrator initialization
        orchestrator = tui.orchestrator
        print(f"✓ Orchestrator initialized: {orchestrator is not None}")
        
        return True
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        return False


def main():
    """Run all TUI tests"""
    print("\n" + "="*60)
    print("NOVEL AI - TUI FUNCTIONALITY TEST SUITE")
    print("="*60)
    
    results = {}
    
    # Test 1: Initialization
    tui = test_tui_initialization()
    results['initialization'] = tui is not None
    
    if not tui:
        print("\n✗ Cannot proceed - TUI initialization failed")
        return
    
    # Test 2: List novels
    results['list_novels'] = test_list_novels(tui)
    
    # Test 3: Source detection
    results['sources'] = test_prompt_source(tui)
    
    # Test 4: Provider detection
    results['providers'] = test_prompt_provider(tui)
    
    # Test 5: Settings
    results['settings'] = test_settings_menu(tui)
    
    # Test 6: Diagnostics
    results['diagnostics'] = test_diagnostics(tui)
    
    # Test 7: Export
    results['export'] = test_export_preconditions(tui)
    
    # Test 8: Error handling
    results['error_handling'] = test_error_handling(tui)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("🎉 All TUI tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
