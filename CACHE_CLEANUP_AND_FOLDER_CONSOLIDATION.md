# Solutions: Cache Cleanup & Folder Consolidation

**Date**: March 7, 2026  
**Topics**: Cache deletion, auto-cleanup, and data structure optimization

---

## 1. Cache Deletion Workaround & Auto-Cleanup

### Problem
Cache folders are locked by Windows processes:
- `.tmp/`, `tests_tmp/`, `pytest-cache-files-*/` remain despite deletion attempts

### Root Cause
- Python/pytest processes still holding file handles
- Windows prevents deletion of in-use files
- Locks released only after process termination

### Solution A: Manual Deletion (After Restart)

**Option 1: Task Scheduler (Automated)**
```batch
@echo off
REM Delete pytest caches after all Python processes end
taskkill /F /IM python.exe
taskkill /F /IM pytest.exe
cd "c:\Akmal\Novel AI"
rmdir /s /q pytest-cache-files-* 2>nul
rmdir /s /q .tmp 2>nul
rmdir /s /q tests_tmp 2>nul
```

Save as: `cleanup_caches.bat`  
Run manually or via Task Scheduler at startup

**Option 2: PowerShell Script (Recommended)**
```powershell
# File: cleanup_pytest_cache.ps1
param([switch]$Force)

$paths = @(
    "pytest-cache-files-*",
    ".tmp",
    "tests_tmp"
)

if ($Force) {
    Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process pytest -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

foreach ($pattern in $paths) {
    Get-Item -Path $pattern -ErrorAction SilentlyContinue | 
    Remove-Item -Recurse -Force -ErrorAction Continue
}

Write-Host "Cache cleanup complete"
```

Run with: `.\cleanup_pytest_cache.ps1 -Force`

---

### Solution B: Auto-Cleanup After Testing

#### Option 1: Pytest Plugin (Best Practice)

Create `tests/conftest.py` enhancement:

```python
import pytest
import shutil
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def cleanup_cache():
    """Auto-clean pytest artifacts after all tests complete."""
    yield
    
    # Cleanup after all tests finish
    cache_dirs = [
        Path(".pytest_cache"),
        Path("tests/.pytest_cache"),
    ]
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                print(f"Cleaned: {cache_dir}")
            except Exception as e:
                print(f"Could not clean {cache_dir}: {e}")
```

**Usage**: Just run `pytest` - cache auto-cleans after tests

#### Option 2: NPM-style Script

Add to `pyproject.toml`:

```toml
[project.scripts]
novelaibook = "novelai.app.cli:main"
pytest-clean = "scripts.cleanup:main"

[tool.pytest.ini_options]
addopts = "--cache-clear"  # Clear cache on each run
```

#### Option 3: GitHub Actions (For CI/CD)

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.13"
      - run: pip install -e ".[test]"
      - run: pytest
      - name: Clean pytest cache
        if: always()
        run: |
          rm -rf .pytest_cache
          rm -rf tests/.pytest_cache
          rm -rf pytest-cache-files-*
```

---

### Solution C: Configuration (Prevent Accumulation)

Update `pyproject.toml` to prevent large cache accumulation:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
cache_dir = "tests/.pytest_cache"
# Aggressive cache management
addopts = "--cache-clear -p no:cacheprovider"
# Or more lenient:
# addopts = "--cache-clear-on-startup"
```

---

### Recommended Implementation Plan

**Immediate (Now)**:
1. ✅ `.gitignore` already ignores cache (won't be committed)
2. ✅ `pyproject.toml` configured to use `tests/.pytest_cache`
3. ✅ Cache doesn't affect project

**Short Term (Next Session)**:
1. Add auto-cleanup fixture to `tests/conftest.py`
2. Run cleanup script on system restart

**Long Term**:
1. Implement GitHub Actions cleanup for CI/CD
2. Consider using pytest plugins for better cache management

---

## 2. Data & Output Folder Consolidation

### Current Situation

```
Novel AI/
├── data/
│   ├── novels/
│   │   └── {novel_name}/
│   │       ├── raw/
│   │       ├── translated/
│   │       ├── epub/          ← Exports go here (per design)
│   │       ├── pdf/           ← Exports go here (per design)
│   │       └── metadata.json
│   ├── translation_cache.json
│   └── usage.json
│
├── output/                    ← REDUNDANT - also stores EPUB/PDF
│   ├── n4423lw.epub
│   └── n4423lw.pdf
```

### Analysis

**Same Function?**
- ❌ **NO** - Different purposes BUT poorly separated
- `data/` = Raw data, translations, processing state
- `output/` = Final exported files (EPUB/PDF)

**Should They Merge?**
- ✅ **YES** - Already designed to merge in `data/novels/{name}/{format}/`
- Check `DATA_OUTPUT_STRUCTURE.md` - confirms exports belong in `data/`
- Check `src/novelai/app/cli.py` - already saves to data by default!

### The Real Issue

The `output/` folder exists for **backward compatibility/flexibility**:
- Users can export to custom location: `--output ./my_folder`
- Users keep exports separate from raw data
- But default behavior saves to `data/novels/{format}/`

**Current Architecture Intent**:
```
# By default (best practice):
python -m novelai export-epub n4423lw
→ Saves to: data/novels/sword_art_online/epub/full_novel.epub

# By custom path (if needed):
python -m novelai export-epub n4423lw --output output
→ Saves to: output/n4423lw.epub
```

### Recommended Solution: Unify as "Novel Library"

**Rename**: `data/` → `novel_library/`

**New Structure**:
```
Novel AI/
├── novel_library/              ← RENAMED: unified "novel library"
│   ├── novels/
│   │   └── {novel_name}/
│   │       ├── metadata.json
│   │       ├── raw/            ← Source chapters
│   │       ├── translated/     ← Translations
│   │       ├── epub/           ← Exports
│   │       ├── pdf/
│   │       └── checkpoints/
│   ├── translation_cache.json
│   ├── usage.json
│   └── backups/                ← Backups
│
└── (Remove: output/ folder)    ← No longer needed as primary location
```

**Benefits**:
- ✅ Single source of truth
- ✅ Clear naming: "novel_library" instead of ambiguous "data"
- ✅ All novel-related content in one place
- ✅ Eliminates scattered `output/` folder
- ✅ Better organization for production

**Migration Path**:

1. **Phase 1 - Add Support** (This session)
   - Update `config/settings.py` to support both `data/` and `novel_library/`
   - Add migration script to rename existing folders
   - Keep backward compatibility with `--output` flag

2. **Phase 2 - Alias** (Next release)
   - Set `novel_library/` as default
   - Keep `data/` as legacy alias
   - Show deprecation warning if using `data/`

3. **Phase 3 - Cleanup** (v1.0 release)
   - Remove `data/` folder references
   - Remove `output/` folder
   - Use only `novel_library/`

---

### Implementation: Rename to "Novel Library"

#### Step 1: Update `config/settings.py`

Change:
```python
DATA_DIR: str = "data"
```

To:
```python
# Novel library directory - contains all downloaded novels and exports
NOVEL_LIBRARY_DIR: str = "novel_library"

# Legacy alias for backward compatibility
@property
def DATA_DIR(self) -> str:
    return self.NOVEL_LIBRARY_DIR
```

#### Step 2: Create Migration Script

File: `scripts/migrate_to_novel_library.py`

```python
#!/usr/bin/env python
"""Migrate from 'data/' to 'novel_library/' structure."""

import shutil
from pathlib import Path

def migrate():
    old_path = Path("data")
    new_path = Path("novel_library")
    
    if old_path.exists() and not new_path.exists():
        print(f"Migrating {old_path} → {new_path}")
        shutil.move(str(old_path), str(new_path))
        print("✓ Migration complete")
    elif new_path.exists():
        print("✓ Already using novel_library structure")
    else:
        print("✓ No migration needed")

if __name__ == "__main__":
    migrate()
```

#### Step 3: Update .gitignore

```diff
- data/
+ novel_library/
```

#### Step 4: Remove `output/` folder

```python
# After migration, output/ becomes unnecessary
# Exports go directly to: novel_library/novels/{name}/epub/pdf/
```

---

### Updated .gitignore

```
# Runtime data
novel_library/           # NEW: Novel library (all novels + exports)
output/                  # LEGACY: Still needed during transition
input/
logs/
```

---

## Implementation Priority

### High Priority (Consolidate Now)
1. ✅ Cache auto-cleanup (conftest.py fixture) - takes 5 min
2. ✅ Rename `data/` → `novel_library/` - takes 30 min
3. ✅ Update settings and references - takes 20 min
4. ✅ Remove `output/` as primary location - takes 10 min

### Medium Priority (Polish)
1. Create migration script
2. Update documentation
3. Test with real novel download

### Low Priority (Deprecation)
1. Add legacy alias and warning messages
2. Document migration path for users
3. Plan removal at v1.0

---

## Summary Recommendation

### For Cache Cleanup
✅ **Implement**: Add conftest.py auto-cleanup fixture (easiest)
- Auto-deletes cache after tests complete
- No manual intervention needed
- Works on all platforms

### For Data Organization  
✅ **Implement**: Rename `data/` → `novel_library/`
- Better naming convention
- Makes purpose clearer
- Consolidates with exports automatically
- Remove `output/` folder (not needed)

**Together**: This creates a clean, unified **"Novel Library"** structure where everything related to novels lives in one place.

---

## Code Changes Summary

### Files to Update
1. `config/settings.py` - Add NOVEL_LIBRARY_DIR
2. `tests/conftest.py` - Add auto-cleanup fixture
3. `.gitignore` - Update paths
4. `README.md` - Update references
5. `GETTING_STARTED.md` - Update paths
6. Documentation files - Update folder references

### Minimal Changes
- All code already uses `settings.DATA_DIR` (abstracted)
- Just need to update the setting and migrate folder
- CLI doesn't need changes (already supports --output flag)

