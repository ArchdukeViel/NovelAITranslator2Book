from __future__ import annotations

import json
from dataclasses import dataclass, field

from novelai.glossary.glossary import GlossaryTerm


@dataclass(frozen=True)
class TranslationRequest:
    source_language: str
    target_language: str
    text: str
    system_prompt: str
    user_prompt: str
    glossary_entries: tuple[GlossaryTerm, ...] = field(default_factory=tuple)
    prompt_glossary_block: str | None = None
    style_preset: str | None = None
    consistency_mode: bool = False
    json_output: bool = False
    honorific_policy: str | None = None
    prompt_template_version: str = ""
    prompt_policy: str | None = None
    prompt_policy_version: str | None = None
    runtime_glossary_conflict_warnings: tuple[str, ...] = ()

    def cache_key(self) -> str:
        payload = {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "text": self.text,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "prompt_glossary_block": self.prompt_glossary_block,
            "glossary_entries": [
                {
                    "source": entry.source,
                    "target": entry.target,
                    "locked": entry.locked,
                    "notes": entry.notes,
                    "status": entry.status,
                    "context_history": list(entry.context_history),
                    "context_summary": entry.context_summary,
                    "occurrence_count": entry.occurrence_count,
                    "last_seen_index": entry.last_seen_index,
                }
                for entry in self.glossary_entries
            ],
            "style_preset": self.style_preset,
            "consistency_mode": self.consistency_mode,
            "json_output": self.json_output,
            "honorific_policy": self.honorific_policy,
            "prompt_template_version": self.prompt_template_version,
            "prompt_policy": self.prompt_policy,
            "prompt_policy_version": self.prompt_policy_version,
            "runtime_glossary_conflict_warnings": list(self.runtime_glossary_conflict_warnings),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
