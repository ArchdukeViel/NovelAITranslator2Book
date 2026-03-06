# Comprehensive Architecture Review: Novel AI Platform

**Review Date:** March 7, 2026  
**Reviewer Role:** Senior Code Architect / Security Auditor  
**Codebase Stage:** Post-generation, pre-production  

---

## 1. EXECUTIVE SUMMARY

This is a **moderately well-intentioned but architecturally problematic** platform. It demonstrates some good patterns (service layer, pipeline abstraction, registry pattern) but contains **critical flaws** that will cause scalability, maintainability, and security issues in production.

**Key Strengths:**
- Clean separation of concerns in service/provider/source layers (structurally)
- Pipeline abstraction with typed context is a good pattern
- Bootstrap registration pattern avoids import-time side effects
- CLI/TUI/web entry points use shared services

**Critical Weaknesses:**
- **Security:** Plain-text API keys persisted to disk; thread-unsafe global state in providers
- **Architecture:** Heavy coupling through global registries; no real dependency injection
- **Testability:** Hard to unit test stages and services due to static registries
- **Scalability:** Inefficient registry design creates new instances on every call
- **Business Logic:** Orchestration logic mixed between services and entrypoints

**Overall Architecture Score: 4.5 / 10**

---

## 2. CRITICAL FLAWS (Must Fix Before Production)

### 2.1 **OpenAI Provider Thread-Safety Vulnerability**

**Location:** [src/novelai/providers/openai_provider.py](src/novelai/providers/openai_provider.py#L20-L35)

```python
# CRITICAL: This modifies global module state
openai.api_key = api_key  # ← THREAD UNSAFE
```

**Problem:** 
- Multiple concurrent translation requests will race to set `openai.api_key`
- In multi-user scenarios (web server), one user's API key can overwrite another's
- OpenAI SDK is not thread-safe with this pattern
- No isolation per request or user

**Impact:** Security breach, API quota theft, request misrouting

**Fix Required:**
- Use OpenAI SDK's context manager / client instance per-request
- Never mutate global `openai` module state
- Inject API key at request time, not instance time

---

### 2.2 **Plain-Text API Key Persistence to Disk**

**Location:** [src/novelai/services/settings_service.py](src/novelai/services/settings_service.py#L43-L47)

```python
def set_api_key(self, api_key: str) -> None:
    self.set("provider_api_key", api_key)  # ← Writes plain-text to settings.json
```

**Problem:**
- API keys stored in plain text in `data/settings.json`
- Any process with filesystem access can read secrets
- Git repository may contain committed secrets
- No encryption, no expiration, no revocation

**Impact:** Compromised API keys, billing fraud, service account hijacking

**Fix Required:**
- Move all secrets to environment variables (recommended)
- OR encrypt secrets at rest using OS keyring (keyring library)
- Never persist secrets to JSON files
- Add secret detection pre-commit hook

---

### 2.3 **Web Router Creates Unmanaged StorageService Instance**

**Location:** [src/novelai/web/routers/novels.py](src/novelai/web/routers/novels.py#L6-L7)

```python
router = APIRouter()
storage = StorageService()  # ← Created at module level, outside container
```

**Problem:**
- Web API does not use the DI container
- Creates a separate StorageService instance (bypasses singleton)
- CLI/TUI/Web each have their own storage instances → data inconsistency
- File handle leaks possible
- No way to mock storage in tests

**Impact:** Data inconsistency, file descriptor exhaustion, untestable code

**Fix Required:**
- Inject storage from container into router
- Use FastAPI dependency injection system
- Remove module-level instantiation

---

### 2.4 **Pipeline Stages Not Dependency-Injected**

**Location:** [src/novelai/services/translation_service.py](src/novelai/services/translation_service.py#L14-L27)

```python
def __init__(self, pipeline: TranslationPipeline | None = None) -> None:
    self.pipeline = pipeline or TranslationPipeline(
        stages=[
            FetchStage(),           # ← Created with defaults
            ParseStage(),           # ← Created with defaults
            SegmentStage(),         # ← Created with defaults
            TranslateStage(),       # ← Created with defaults
            PostProcessStage(),     # ← Created with defaults
        ]
    )
```

**Problem:**
- Stages are hardcoded, not injectable
- TranslateStage internally creates TranslationCache, settings_service, usage_service
- Cannot compose different pipelines for different use cases
- Cannot mock stages for testing
- Adding a new stage requires modifying this file

**Impact:** Not composable, not testable, will be painful to extend

**Fix Required:**
- Make pipeline stages fully injectable
- Pass cache, settings, usage as constructor params
- Allow pipeline composition from outside

---

### 2.5 **NovelOrchestrationService Duplicates Translation Logic**

**Location:** [src/novelai/services/novel_orchestration_service.py](src/novelai/services/novel_orchestration_service.py#L45-L90)

**Problem:**
- `translate_chapters()` manually orchestrates the pipeline
- Should delegate to `TranslationService`
- Business logic scattered between service and orchestrator
- Same logic would be repeated if web API needed to translate

**Code Duplication:**
```python
# In NovelOrchestrationService.translate_chapters():
result = await self.translation.translate_chapter(
    source_adapter=source,
    chapter_url=chapter.get("url"),
    provider_key=provider_key,
    provider_model=provider_model,
)

# But TranslationService.translate_chapter() already does this!
# This is just a wrapper.
```

**Impact:** Hard to maintain orchestration logic; inconsistent behavior if changed in one place

**Fix Required:**
- Make NovelOrchestrationService a thin orchestrator
- Push business logic into TranslationService
- Separate "what to translate" from "how to translate"

---

### 2.6 **Global Registry Creates New Instance Every Call**

**Location:** [src/novelai/providers/registry.py](src/novelai/providers/registry.py#L18-L25)

```python
def get_provider(key: str | None = None) -> TranslationProvider:
    effective_key = key or settings.PROVIDER_DEFAULT
    factory = _PROVIDER_REGISTRY.get(effective_key)
    if factory is None:
        raise KeyError(f"No provider registered for key: {effective_key}")
    
    return factory()  # ← Creates NEW instance every time!
```

**Problem:**
- `factory()` creates a new provider instance on every call
- OpenAI provider is created fresh for each translation
- Inefficient; wastes memory
- Any state in provider is lost between calls
- Makes caching/pooling impossible

**Impact:** Memory pressure, impossible to implement connection pooling, slow

**Fix Required:**
- Distinguish between "factory pattern" and "singleton pattern"
- Most providers should be singletons or cached
- Only recreate if needed for stateless behavior

---

### 2.7 **Glossary Never Actually Integrated Into Pipeline**

**Location:** [src/novelai/pipeline/stages/post_process.py](src/novelai/pipeline/stages/post_process.py)

```python
class PostProcessStage(PipelineStage):
    async def run(self, context: PipelineContext) -> PipelineContext:
        # Placeholder: implement glossary replacement, formatting rules, etc.
        context.final_text = "\n\n".join(context.translations)
        return context
```

**Problem:**
- Glossary is defined but never used
- PostProcessStage is a placeholder doing simple joining
- No glossary passed to stage
- Cannot apply term substitutions
- No way to compose multiple glossaries

**Impact:** Glossary feature is dead code; inconsistent translations

**Fix Required:**
- Inject glossary into PostProcessStage
- Implement glossary.translate(text) application
- Make glossary selection configurable

---

### 2.8 **Storage Layer is Over-Generic and Domain-Leaky**

**Location:** [src/novelai/services/storage_service.py](src/novelai/services/storage_service.py)

**Problems:**
- Named "StorageService" but really is "NovelStorageService"
- Hardcodes novel folder structure, index format, chapter naming
- Mixes storage concerns with business logic (hash comparison, folder renaming based on metadata)
- Cannot be reused for other domains (users, settings, cache)
- File path construction is scattered throughout

**Code Example of Leakiness:**
```python
def _compute_folder_name(self, novel_id: str, metadata: dict[str, Any]) -> str:
    """Business logic: prefer translated_title > title > novel_id"""
    # This is BUSINESS LOGIC in storage layer!
```

**Impact:** Cannot add storage for other entities; hard to test; not reusable

**Fix Required:**
- Rename to `NovelStorageService`
- Extract folder strategy to separate class
- Create generic `StorageRepository` base for other entities

---

### 2.9 **No Retry/Fallback for Provider Failures**

**Location:** [src/novelai/pipeline/stages/translate.py](src/novelai/pipeline/stages/translate.py#L40-L60)

```python
async def _translate_chunk(self, provider_key: str, model: str, chunk: str) -> str:
    provider = get_provider(provider_key)
    cached = self._cache.get(chunk, provider.key, model)
    if cached is not None:
        return cached

    result = await provider.translate(prompt=chunk, model=model)  # ← NO RETRY!
    # If this fails, entire translate_chapters() fails
```

**Problem:**
- No retry logic for transient failures
- No fallback provider if primary fails
- No circuit breaker pattern
- Single API failure crashes the whole pipeline

**Impact:** Pipeline fragility; cannot handle temporary API outages

**Fix Required:**
- Add retry decorator with exponential backoff
- Support fallback providers
- Add circuit breaker pattern
- Graceful degradation

---

### 2.10 **TUI Calls bootstrap() Again (Redundant and Fragile)**

**Location:** [src/novelai/tui/app.py](src/novelai/tui/app.py#L19-L21)

```python
def __init__(self) -> None:
    # Ensure providers/sources are registered before any user interaction.
    bootstrap()  # ← Already called by CLI!
```

**Location:** [src/novelai/app/cli.py](src/novelai/app/cli.py#L65)

```python
# Ensure providers/sources are registered before we use them.
bootstrap()  # ← Called here too
```

**Problem:**
- bootstrap() can be called multiple times
- No guard against duplicate registration (overwrites)
- Each entry point independently ensures bootstrap
- Fragile: easy to forget in new entry point

**Impact:** Fragile initialization; silent duplication bugs

**Fix Required:**
- Make bootstrap() idempotent
- Call once at application startup
- Use guard flag to prevent re-registration

---

## 3. HIGH-PRIORITY IMPROVEMENTS (Fix in Phase 1-2)

### 3.1 **Pipeline Context Conflates Multiple Concerns**

**Location:** [src/novelai/pipeline/context.py](src/novelai/pipeline/context.py)

```python
@dataclass
class PipelineContext:
    source_adapter: SourceAdapter  # ← Shouldn't be here
    chapter_url: str               # ← Should be separate
    provider_key: Optional[str]
    provider_model: Optional[str]
    raw_text: Optional[str]
    normalized_text: Optional[str]
    chunks: List[str]
    translations: List[str]
    final_text: Optional[str]
    metadata: Dict[str, Any]
```

**Problem:**
- Mixes input config (source_adapter, chapter_url) with working state
- source_adapter shouldn't be serializable/storable
- Makes context hard to deserialize from storage
- Unclear what's input vs intermediate vs output

**Impact:** Confusion about stage responsibilities; hard to extend

**Fix Required:**
- Split into: `PipelineConfig`, `PipelineState`, `PipelineOutput`
- Or: `PipelineInput`, `PipelineWipContext`, `PipelineResult`

---

### 3.2 **No Proper Error Boundaries / Error Handling**

**Problem:**
- No custom exception hierarchy
- No error recovery in stages
- Storage errors propagate uncaught
- Web API has no error middleware

**Example:** [src/novelai/web/routers/novels.py](src/novelai/web/routers/novels.py) has `raise HTTPException` but no other error handling

**Fix Required:**
- Create `novelai.core.errors` module with:
  - `NovelAIError` (base)
  - `ProviderError`, `SourceError`, `StorageError`, `PipelineError`
- Add error handling middleware to FastAPI
- Implement error context enrichment

---

### 3.3 **Incomplete Abstraction: Source Adapter is Too Thin**

**Location:** [src/novelai/sources/base.py](src/novelai/sources/base.py)

```python
class SourceAdapter(ABC):
    @abstractmethod
    async def fetch_metadata(self, url: str) -> dict[str, Any]:
        ...
    
    @abstractmethod
    async def fetch_chapter(self, url: str) -> str:
        ...
```

**Problems:**
- Only two methods; interface will explode as requirements grow
- No pagination support (how to list chapters?)
- No retry/timeout configuration
- No rate limiting per-source
- No way to handle source-specific errors
- `url` is misleading; some sources use IDs, not URLs

**Future Pain Points:**
- Adding source capability discovery (what formats does it provide?)
- Adding source-specific preprocessors
- Adding source-specific retry policies

**Fix Required:**
- Add more required methods: `capabilities()`, `extract_novel_id()`, `list_chapters()`
- Add optional hooks: `before_fetch()`, `after_fetch()`
- Create `SourceConfig` class for per-source settings

---

### 3.4 **Export Design is Rigid**

**Location:** [src/novelai/services/export_service.py](src/novelai/services/export_service.py)

```python
class ExportService:
    def __init__(self) -> None:
        self.epub_exporter = EPUBExporter()  # ← Hardcoded
        self.pdf_exporter = PDFExporter()    # ← Hardcoded

    def export_epub(self, ...):
        return self.epub_exporter.export(...)
    
    def export_pdf(self, ...):
        return self.pdf_exporter.export(...)
```

**Problems:**
- Each exporter implementation is hardcoded
- Adding a new exporter requires editing ExportService
- Method names are format-specific (export_epub, export_pdf)
- Should use registry pattern like providers/sources
- No exporter metadata (supported formats, options)

**Pain Points:**
- Adding MOBI export? Have to edit ExportService
- Adding export format templates? Can't compose
- Cannot list available formats dynamically

**Fix Required:**
- Create `ExporterRegistry` (like SourceRegistry, ProviderRegistry)
- Generic `export(format, chapters, options)` method
- Exporter capability/option discovery

---

### 3.5 **SettingsService Violates Separation of Concerns**

**Location:** [src/novelai/services/settings_service.py](src/novelai/services/settings_service.py)

```python
class SettingsService:
    """Persistence for runtime settings (provider, model, API keys, etc.)."""
```

**Problems:**
- Mixes environment config (AppSettings) with user preferences
- No distinction between:
  - System settings (read via env vars from deployment)
  - User preferences (persisted to disk)
  - Secrets (should never be in SettingsService)
- Makes it unclear which is which
- Secrets are persisted (not externalized)

**Design Flaws:**
```python
# These three types are conflated:
settings.get_provider_key()      # ← User pref
settings.get_api_key()           # ← Secret! Should not persist
settings.PROVIDER_DEFAULT        # ← App config from env
```

**Fix Required:**
- Create `PreferencesService` (user prefs, persisted, optional)
- Keep `AppSettings` (env config only, never persisted)
- Move secrets = environment variables only
- Create `SecretStore` interface for potential keyring support

---

### 3.6 **Missing Chapter State Machine**

**Problem:**
- No formal chapter states: SCRAPED, PARSED, TRANSLATED, EXPORTED
- Cannot query "which chapters are ready for export?"
- Scrape logic checks file existence instead of state
- Cannot retry from intermediate stages
- Storage layer unsure what's complete

**Example Problem:**
```python
# In NovelOrchestrationService.translate_chapters():
existing = self.storage.load_translated_chapter(novel_id, str(chapter_num))
if existing:
    continue  # ← Uses file existence as state, not explicit state
```

**Fix Required:**
- Add `ChapterState` enum: SCRAPED, PARSED, SEGMENTED, TRANSLATED, EXPORTED
- Track state in metadata
- Query methods: `get_chapters_by_state()`
- Audit trail for state transitions

---

## 4. MEDIUM-PRIORITY IMPROVEMENTS

### 4.1 **Naive Chunking Strategy**

**Location:** [src/novelai/pipeline/stages/segment.py](src/novelai/pipeline/stages/segment.py)

```python
context.chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
```

**Problems:**
- Assumes paragraphs are separated by `\n\n` (fragile)
- No configurable chunk size limits
- Large paragraphs exceed token limits for some models
- No overlap for context preservation
- No sentence-aware chunking

**Fix Required:**
- Configurable chunk strategy
- Respect token limits per model
- Support sentence boundaries
- Test with real Japanese text samples

---

### 4.2 **ParseStage is Missing**

**Location:** Cannot find [src/novelai/pipeline/stages/parse.py](src/novelai/pipeline/stages/parse.py)

**Problem:**
- ImportError will occur when TranslationService tries to use ParseStage
- No file exists for it
- No normalization logic (where does normalized_text come from?)

**Fix Required:**
- Implement ParseStage
- Define what normalization means for Japanese web novels
- Test with real samples

---

### 4.3 **Container is a Global Singleton Without Control**

**Location:** [src/novelai/app/container.py](src/novelai/app/container.py)

```python
container = Container()  # ← Global singleton, created immediately
```

**Problems:**
- Hard to override in tests
- Cannot create separate containers for different scenarios
- Lazy initialization makes dependencies flaky (might fail late)
- No validation that all required services are available

**Fix Required:**
- Make container creation explicit and testable
- Support container stacking for test fixtures
- Add validation/health check method

---

### 4.4 **No Logging Framework**

**Problems:**
- Code uses no logging at all (or relies on print)
- No visibility into what pipeline is doing
- Cannot debug production issues
- No audit trail for API calls

**Fix Required:**
- Add Python logging module throughout
- Structured logging (JSON for production)
- Log levels for different concerns
- Audit logging for API key usage, translations

---

### 4.5 **Translation Cache is Ad-Hoc**

**Location:** [src/novelai/services/translation_cache.py](src/novelai/services/translation_cache.py)

**Likely Problems:**
- In-memory only (lost on restart)
- No TTL/expiration
- Could use unbounded memory
- No cache statistics
- Per-stage, not shared

**Fix Required:**
- Add Redis or persistent cache option
- TTL support
- Memory limit + LRU eviction
- Cache statistics
- Shared across stages

---

### 4.6 **DummyProvider is Too Minimal**

**Location:** [src/novelai/providers/dummy_provider.py](src/novelai/providers/dummy_provider.py)

**Problem:**
- Cannot use for real end-to-end testing
- Doesn't validate input formats
- Doesn't simulate API behavior

**Fix Required:**
- Make DummyProvider more realistic
- Add deterministic responses for testing
- Simulate failures for testing error handling

---

## 5. DUPLICATE / OVERLAPPING LOGIC FOUND

### 5.1 **Bootstrap Logic is Entry-Point Dependent**

| Location | Pattern |
|----------|---------|
| [src/novelai/app/cli.py](src/novelai/app/cli.py#L65) | Calls `bootstrap()` |
| [src/novelai/tui/app.py](src/novelai/tui/app.py#L19) | Calls `bootstrap()` again |
| [src/novelai/web/api.py](src/novelai/web/api.py#L7) | Calls `bootstrap()` again |

**Impact:** Fragile, error-prone, silent duplication possible

**Fix:** Single entry point in app startup

---

### 5.2 **Metadata Loading Scattered Across Layers**

| Service | Method | Storage Call |
|---------|--------|------|
| NovelOrchestrationService | scrape_chapters | `storage.load_metadata()` |
| NovelOrchestrationService | translate_chapters | `storage.load_metadata()` |
| TranslationService | translate_chapter | (none - should check?) |

**Impact:** Inconsistent metadata access patterns

---

### 5.3 **Provider Instance Creation**

| Location | Pattern |
|----------|---------|
| [src/novelai/providers/registry.py](src/novelai/providers/registry.py#L22) | `factory()` creates instance |
| [src/novelai/pipeline/stages/translate.py](src/novelai/pipeline/stages/translate.py#L40) | `get_provider(provider_key)` |

**Impact:** Unclear whether providers are singletons or ephemeral

---

### 5.4 **Chapter Number Parsing**

| Location | Purpose |
|----------|---------|
| [src/novelai/utils/chapter_selection.py](src/novelai/utils/chapter_selection.py) | Utility to parse "1-3;5" |
| NovelOrchestrationService | Uses it in scrape_chapters, translate_chapters |

**Issue:** Chapter selection parsing is tightly coupled to orchestration logic, not reusable for queries

---

## 6. API BLEED / BOUNDARY VIOLATIONS FOUND

### 6.1 **Web Router Creates Storage Directly**

**File:** [src/novelai/web/routers/novels.py](src/novelai/web/routers/novels.py#L6-L7)

```python
storage = StorageService()  # ← Should inject from container
```

**Violation:** Bypasses dependency injection container

**Risk:** 
- Data inconsistency (different instances)
- Cannot mock in tests
- Cannot centralize storage configuration

---

### 6.2 **Pipeline Exposes SourceAdapter in Context**

**File:** [src/novelai/pipeline/context.py](src/novelai/pipeline/context.py#L23)

```python
source_adapter: SourceAdapter  # ← Public property
```

**Violation:** Stages can bypass abstraction and call source_adapter directly

**Example Problem:** Stage could call `source_adapter.fetch_chapter()` directly instead of using FetchStage

---

### 6.3 **TranslateStage Reaches Into Global Registry**

**File:** [src/novelai/pipeline/stages/translate.py](src/novelai/pipeline/stages/translate.py#L40)

```python
provider = get_provider(provider_key)  # ← Reaches into global registry
```

**Violation:** Stage has hidden dependency on registry

**Risk:**
- Cannot test stage without initializing registry
- Cannot mock provider
- Stage couples to registry pattern

**Fix:** Inject provider or provider factory into stage

---

### 6.4 **TranslateStage Uses Global Settings**

**File:** [src/novelai/pipeline/stages/translate.py](src/novelai/pipeline/stages/translate.py#L26-L32)

```python
def __init__(
    self,
    concurrency: Optional[int] = None,
    cache: TranslationCache | None = None,
    settings_service: SettingsService | None = None,
    usage_service: UsageService | None = None,
) -> None:
    self._concurrency = concurrency or settings.TRANSLATION_CONCURRENCY  # ← Reaches into global
```

**Violation:** Falls back to global `settings` if not injected

**Risk:** Inconsistent behavior between test and production

---

### 6.5 **NovelOrchestrationService Calls get_source() Directly**

**File:** [src/novelai/services/novel_orchestration_service.py](src/novelai/services/novel_orchestration_service.py#L25)

```python
source = get_source(source_key)  # ← Direct registry call
```

**Violation:** Service has hidden dependency on source registry

**Risk:** Untestable without initializing registry

---

### 6.6 **OpenAI Provider Mutates Global Module State**

**File:** [src/novelai/providers/openai_provider.py](src/novelai/providers/openai_provider.py#L31)

```python
openai.api_key = api_key  # ← GLOBAL MUTATION!
```

**Violation:** Thread-unsafe global state

**Risk:** Security vulnerability in multi-user scenarios

---

## 7. SCALABILITY CONCERNS

### 7.1 **Registry Creates New Instances Every Call**

**Current:** `get_provider(key)` creates new instance each time

**Problem:**
- OpenAI provider created fresh with new session → slow
- Memory churn under load
- Cannot implement connection pooling
- Cannot cache partial state

**Solution:**
- Cache provider instances
- Support singleton pattern
- Configurable instance lifecycle

---

### 7.2 **Storage Service Not Connection-Pooled**

**Problem:**
- File I/O not optimized
- No batching of operations
- Each save_chapter -> separate JSON write
- Each load_chapter -> separate JSON read

**Scalability Issue:**
- 1000 chapters = 1000 file writes (serialize, write, flush)
- No transaction support
- No atomic multi-chapter operations

**Solution:**
- Consider database (SQLite for single-machine, Postgres for multi-machine)
- Batch operations
- Connection pooling
- Transactions

---

### 7.3 **Translation Cache is Per-Stage, Not Shared**

**Problem:**
- Each TranslateStage has its own cache
- If two pipelines run in parallel, cache not shared
- memory waste for duplicated translations

**Solution:**
- Centralize cache to container
- Share across all stages
- Consider distributed cache (Redis) for multi-process

---

### 7.4 **No Pagination / Query Methods in Storage**

**Problem:**
- `list_novels()` returns all novels
- No filtering: by source, date, status
- No pagination for large datasets
- Cannot efficiently query "chapters ready for export"

**Solution:**
- Add query builder / filter interface
- Pagination support
- Chapter state queries

---

### 7.5 **Pipeline is Not Parallel-Friendly**

**Problem:**
- Single pipeline processes chapters one-at-a-time
- All translation work serialized in TranslateStage
- Could parallelize across multiple chapters, not just within-chapter

**Solution:**
- Batch chapter processing
- Queue-based distribution
- Worker pool for parallel pipelines

---

## 8. SECURITY / CONFIG CONCERNS

### 8.1 **Plain-Text Secrets in settings.json**

**File:** [src/novelai/services/settings_service.py](src/novelai/services/settings_service.py)

```python
def set_api_key(self, api_key: str) -> None:
    self.set("provider_api_key", api_key)  # ← Plain text
```

**Risk:**
- Git may commit settings.json with keys
- Local filesystem access = key compromise
- No key rotation support
- No audit trail

**Fix:**
- Environment variables only (strongly recommended)
- OR: OS keyring with keyring library
- No .json file storage for secrets

---

### 8.2 **OpenAI API Key Thread Safety Issue**

**File:** [src/novelai/providers/openai_provider.py](src/novelai/providers/openai_provider.py#L31)

```python
openai.api_key = api_key  # ← Race condition
```

**Risk:**
- In web server with multiple concurrent users
- User A's key could be used for User B's request
- Could escalate to wrong account
- Could steal translation prompts across users

**Fix:**
- Use per-request client instance
- Newer OpenAI SDK supports this directly
- Never mutate global module state

---

### 8.3 **No Secret Masking in Logs**

**Problem:**
- If logging is added, API keys could leak into logs
- No automatic secret masking

**Fix:**
- Add secret filter to logging
- Mask API keys in debug output
- Audit trail without exposing secrets

---

### 8.4 **No Rate Limiting or Quota Management**

**Problem:**
- No circuit breaker for provider calls
- No budget/quota enforcement
- Could accidentally run up large bill

**Fix:**
- Add rate limiter decorator
- Implement quota tracking
- Alerts for high usage

---

### 8.5 **Config Inheritance is Unclear**

**Location:** [src/novelai/config/settings.py](src/novelai/config/settings.py)

```python
class AppSettings(BaseSettings):  # ← From pydantic_settings
    PROVIDER_OPENAI_API_KEY: Optional[SecretStr] = Field(None, ...)
```

**Problem:**
- Env var naming convention not documented
- Both `AppSettings` and `SettingsService` are used
- Unclear which takes precedence
- No validation of required fields

**Fix:**
- Document env var naming and precedence
- Centralize all config to single source
- Add startup validation

---

## 9. NAMING / ORGANIZATION ISSUES

### 9.1 **"StorageService" is Too Generic**

**Should be:** `NovelStorageService`

**Reason:** 
- Really stores novels, not generic storage
- May have other storage needs (user prefs, cache)
- Name should match domain

---

### 9.2 **"SourceAdapter" vs "Source" vs "Scraper"**

**Current:** `SourceAdapter` in [src/novelai/sources/base.py](src/novelai/sources/base.py)

**Confusion:**
- Called "adapter" but it's the primary abstraction
- Could be called "Source" or "Scraper"
- "Adapter" suggests it adapts something else

**Recommendation:** Rename to `NovelSource` or `NovelScraper`

---

### 9.3 **"TranslationProvider" vs "Provider"**

**Inconsistency:**
- Class: `TranslationProvider`
- Directory: `providers/`
- Registry: `get_provider()`
- What if there are other provider types in future?

**Fix:** Keep `TranslationProvider` if that's the domain

---

### 9.4 **BaseExporter vs EPUBExporter Naming**

**Inconsistency:**
- Base class: `BaseExporter`
- Subclass: `EPUBExporter`, `PDFExporter`
- Should be: `EPUBExporter extends Exporter`

**Recommendation:** Rename `BaseExporter` → `Exporter`

---

### 9.5 **Pipeline Stages Named Inconsistently**

Currently:
- `FetchStage` ← Verb
- `ParseStage` ← Verb
- `SegmentStage` ← Noun
- `TranslateStage` ← Verb
- `PostProcessStage` ← Adjective + Verb

**Fix:** Use consistent naming (all verbs or all nouns)

---

### 9.6 **"Container" is Too Generic**

**Better:** `ApplicationContainer` or `ServiceContainer`

---

## 10. CONCRETE REFACTOR RECOMMENDATIONS

### Phase 1: Dependency Injection & Config (Weeks 1-2)

**Fix the critical flaws:**

1. **Remove global OpenAI state**
   - Use per-request client instance
   - Update to current OpenAI SDK

2. **Externalize secrets**
   - Move PROVIDER_OPENAI_API_KEY to env only
   - Add logic to read from keyring if needed
   - Remove SettingsService.set_api_key()

3. **Fix web router storage**
   - Inject from container
   - Use FastAPI dependency

4. **Create PreferencesService**
   - Separate from AppSettings
   - Store user preferences (not secrets)
   - Never persist API keys

5. **Make bootstrap idempotent**
   - Add guard flag
   - Call once at app startup
   - Centralize in single place

---

### Phase 2: Composition & Testing (Weeks 3-4)

1. **Inject pipeline stages**
   - Make TranslationService accept stages
   - TranslateStage accepts provider factory (not global registry)
   - All services injectable from container

2. **Create proper error hierarchy**
   - Base: `NovelAIError`
   - Add subclasses for each domain
   - Add error middleware to web layer

3. **Implement ParseStage properly**
   - Define normalization for Japanese text
   - Test with real samples

4. **Create ExporterRegistry**
   - Register exporters like providers/sources
   - Support: export(format, **options)
   - Dynamic format discovery

5. **Split PipelineContext**
   - Input, Working State, Output
   - Cleaner boundaries

---

### Phase 3: Reliability & Scalability (Weeks 5-6)

1. **Add retry/fallback logic**
   - Provider call retry decorator
   - Fallback provider support
   - Circuit breaker pattern

2. **Improve storage**
   - Query builder / filters
   - Chapter state queries
   - Consider database for scalability

3. **Implement glossary in PostProcessStage**
   - Inject glossary from container
   - Apply translations
   - Support multi-glossary per project

4. **Add logging throughout**
   - Structured JSON logging
   - Log levels for concerns
   - Audit logging for API calls

5. **Improve caching**
   - Shared cache in container
   - Redis support option
   - Cache statistics

---

### Phase 4: Security & Quality (Weeks 7-8)

1. **Secret masking in logs**
   - Add logging filter
   - Mask API keys

2. **Rate limiting / quota**
   - Add rate limiter decorator
   - Track usage, enforce limits
   - Cost tracking

3. **Comprehensive test suite**
   - Unit tests for stages
   - Integration tests for pipeline
   - Mock providers/sources
   - Fixture containers

4. **Documentation**
   - Architecture decision records
   - Config guide
   - Extension guide

5. **Pre-commit hooks**
   - Detect secret patterns
   - Enforce code quality
   - Type checking

---

## 11. SUGGESTED IMPROVED DEPENDENCY RULES

### Current State (Problematic)

```
cli → bootstrap
tui → bootstrap
web → bootstrap        (all call bootstrap again)

cli → NovelOrchestrationService → get_source() (hidden)
tui → NovelOrchestrationService → get_source() (hidden)

web.routers.novels → StorageService() (creates own)

TranslateStage → get_provider() (hidden registry dependency)
TranslateStage → settings (global)

TranslationService → hard-coded stages (not injectable)
```

### Proposed Improved State

```
main.py (or app startup)
  ├─ container.setup()           # ← Single place
  ├─ bootstrap()                 # ← Called once
  ├─ app = create_app(container) # ← Pass container
  └─ app.run()

container:
  ├─ storage = StorageService()           # ← Singleton
  ├─ cache = TranslationCache()           # ← Singleton
  ├─ settings = AppSettings()             # ← From env
  ├─ prefs = PreferencesService()         # ← From disk, no secrets
  ├─ orchestrator = NovelOrchestrationService(storage, translation)
  ├─ translation = TranslationService(
  │    stages=[                           # ← Injectable
  │      FetchStage(),
  │      ParseStage(),
  │      SegmentStage(),
  │      TranslateStage(provider_factory=container.get_provider_factory),
  │      PostProcessStage(glossary=container.glossary),
  │    ]
  │  )
  ├─ export = ExportService(exporter_registry)
  └─ [other services]

cli → container → services → pipeline
tui → container → services → pipeline
web → container → services → pipeline

(No hidden dependencies)
(All testable with mock container)
(All injectable)
```

---

## 12. SUGGESTED MISSING TESTS

### Unit Tests

```python
# tests/unit/providers/test_openai_provider.py
- test_translate_success()
- test_translate_api_error()
- test_api_key_thread_safety()  ← NEW!
- test_api_key_not_global()     ← NEW!

# tests/unit/pipeline/stages/
- test_fetch_stage()
- test_parse_stage_normalizes_japanese()  ← NEW!
- test_segment_stage_respects_chunk_size()  ← NEW!
- test_translate_stage_uses_cache()
- test_translate_stage_retries_on_failure()  ← NEW!
- test_post_process_applies_glossary()  ← NEW!

# tests/unit/services/
- test_storage_service_isolation()
- test_translation_service_composes_stages()  ← NEW!
- test_export_service_registry_pattern()  ← NEW!
- test_settings_service_no_secrets()  ← NEW!
- test_preferences_vs_settings_separation()  ← NEW!

# tests/unit/web/
- test_novels_router_uses_container()  ← NEW!
- test_no_storage_created_in_module()  ← NEW!
```

### Integration Tests

```python
# tests/integration/pipeline/
- test_full_translation_pipeline_e2e()
- test_pipeline_with_dummy_provider()
- test_pipeline_with_glossary()  ← NEW!
- test_pipeline_error_handling_and_recovery()  ← NEW!

# tests/integration/services/
- test_orchestration_scrape_translate_export()

# tests/integration/web/
- test_web_api_full_flow()
```

### Fixtures

```python
# tests/conftest.py
- @pytest.fixture def container_for_tests()  ← NEW!
- @pytest.fixture def mock_provider()  ← NEW!
- @pytest.fixture def mock_source()
- @pytest.fixture def temp_storage()
```

---

## 13. FINAL ARCHITECTURE SCORE: 4.5 / 10

### Breakdown

| Category | Score | Notes |
|----------|-------|-------|
| **Separation of Concerns** | 5/10 | Some good patterns (services, pipeline) but boundaries violated (web router, global state) |
| **Dependency Management** | 3/10 | Pseudo-DI container, hidden dependencies via global registry, not testable |
| **Abstraction Quality** | 5/10 | Good base classes but incomplete (no retry patterns, no composability) |
| **Error Handling** | 2/10 | No custom errors, no recovery, silent failures possible |
| **Security** | 2/10 | Plain-text secrets, global state mutations, thread-safety issues |
| **Scalability** | 4/10 | Registry creates new instances, storage not optimized, no pagination |
| **Testability** | 3/10 | Hard to mock global state, hidden dependencies, no test fixtures |
| **Naming** | 6/10 | Generally reasonable but some inconsistencies (SourceAdapter, BaseExporter) |
| **Documentation** | 3/10 | Minimal docstrings, no architecture docs, no extension guide |
| **Future-Proofing** | 4/10 | Will be painful to add: new providers, sources, export formats, web features |

### Why Not Higher?

**Critical Issues Preventing 7+:**
- Thread-unsafe provider implementation
- Plain-text secret persistence
- Global mutable state throughout
- Missing error handling framework
- Hidden dependencies in stages
- Web layer bypasses DI

**Verdict:** The project has good bones (service layer, pipeline abstraction) but **will fail in production** without addressing security and testability issues. The foundation is solid enough to build on, but requires **Phase 1 refactoring before adding features**.

---

## 14. PRIORITIZED REFACTOR ROADMAP

### CRITICAL (Before Any Production Deployment)

1. **Fix OpenAI thread-safety** (2 hours) — 🔴 SECURITY
   - Use per-request client instances
   - Remove global state mutation
   - Add tests for concurrent calls

2. **Externalize secrets** (3 hours) — 🔴 SECURITY
   - Remove SettingsService.set_api_key()
   - Move to environment only
   - Add keyring support (optional)

3. **Fix web router storage** (1 hour) — 🟠 HIGH
   - Inject from container
   - Remove module-level instance

4. **Make bootstrap idempotent** (1 hour) — 🟠 HIGH
   - Add guard flag
   - Call once at startup

### HIGH (Before Public Beta / Multi-User)

5. **Inject pipeline stages** (4 hours) — 🟠 HIGH
   - Make TranslationService accept stages
   - Fix TranslateStage provider dependency
   - Add container fixture for tests

6. **Create error hierarchy** (3 hours) — 🟠 HIGH
   - NovelAIError base class
   - Domain-specific errors
   - Error middleware

7. **Implement ParseStage** (3 hours) — 🟠 HIGH
   - Define normalization for Japanese
   - Test with real samples

### MEDIUM (Before Heavy Feature Development)

8. **Create PreferencesService** (2 hours) — 🟡 MEDIUM
   - Separate from AppSettings
   - No secrets

9. **ExporterRegistry** (2 hours) — 🟡 MEDIUM
   - Follow provider/source pattern
   - Dynamic format discovery

10. **Split PipelineContext** (2 hours) — 🟡 MEDIUM
    - Input / State / Output
    - Type clarity

11. **Add logging** (3 hours) — 🟡 MEDIUM
    - Structured logging
    - Log levels

12. **Implement glossary** (2 hours) — 🟡 MEDIUM
    - Inject into PostProcessStage
    - Test with samples

### ONGOING

13. **Add retry/fallback** (4 hours) — 🟡 MEDIUM
14. **Improve storage queries** (4 hours) — 🟡 MEDIUM
15. **Comprehensive tests** (8+ hours) — 🟡 MEDIUM
16. **Rate limiting / quota** (2 hours) — 🟡 MEDIUM
17. **Documentation** (4 hours) — 🟡 MEDIUM

**Total Estimated Time:** 50-60 hours

---

## 15. FILES TO RENAME / REORGANIZE

### Renames

| Current | Proposed | Reason |
|---------|----------|--------|
| `StorageService` | `NovelStorageService` | Too generic, domain-specific |
| `SourceAdapter` | `NovelSource` | "Adapter" implies it adapts something |
| `BaseExporter` | `Exporter` | Cleaner naming |
| `Container` | `ApplicationContainer` | Too generic |

### Reorganize

**Move:**
- `services/settings_service.py` → `config/preferences_service.py` (new)
- Keep `config/settings.py` for env-based config only

**Split:**
- `pipeline/context.py` → `pipeline/context.py`, `pipeline/input.py`, `pipeline/output.py`
- Or rename to `PipelineState` or use separate types

**Extract:**
-  `errors/` → Create new directory for error hierarchy

---

## CONCLUSION

This is a **good-intentioned project with solid patterns but critical flawed execution**. The service layer, pipeline abstraction, and registry patterns show architectural thinking. However, **security vulnerabilities, testability gaps, and hidden global dependencies make it unsuitable for production**.

**Most dangerous issues:**
1. Thread-unsafe OpenAI API key (security breach)
2. Plain-text secrets persisted to disk (key compromise)
3. Web router creates unmanaged instances (data inconsistency)

**Most painful long-term issues:**
1. Global state everywhere (untestable)
2. Hidden dependencies in stages (hard to mock)
3. Hardcoded pipeline composition (not composable)

**Recommendation:** Execute Phase 1 and Phase 2 refactoring before accepting new features. The foundation is worth saving; the surface is not ready for production.

