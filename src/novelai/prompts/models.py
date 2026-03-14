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
    style_preset: str | None = None
    consistency_mode: bool = False
    json_output: bool = False

    def cache_key(self) -> str:
        payload = {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "text": self.text,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
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
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
