from __future__ import annotations

from textwrap import dedent

PROMPT_TEMPLATE_VERSION = "v4"

# JP-EN prompt quality policy identity (REQ-10).
# Bumped when output-shaping instructions change in a way that can
# affect translation results. Cache identity includes this version
# so old cached translations are not reused after policy changes.
JP_EN_PROMPT_POLICY = "jp_en_quality"
JP_EN_PROMPT_POLICY_VERSION = "jp_en_quality_v3"

# Language aliases for JP-EN activation (REQ-2).
JP_EN_SOURCE_LANGUAGE_ALIASES = frozenset({"ja", "japanese"})
JP_EN_TARGET_LANGUAGE_ALIASES = frozenset({"en", "english"})

MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE = dedent(
    """
    You are an expert literary translator specializing in novels, web novels, light novels, and serialized fiction.

    Translate the user's {source_language} fiction text into natural, fluent {target_language} while preserving the original meaning, tone, pacing, characterization, and paragraph structure.

    Core rules:
    - Preserve all meaning exactly. Do not omit, summarize, censor, soften, or add information.
    - Keep the same paragraph breaks as the source unless the user explicitly requests otherwise.
    - Preserve every [CHAPTER ...] and [P ...] marker exactly as-is.
    - Every source [P pNNNN] marker must appear exactly once in the output, in source order.
    - If a paragraph cannot be translated, still output its [P pNNNN] marker and leave the translated body blank rather than omitting the marker.
    - Translate into smooth, readable {target_language} prose rather than word-for-word literal output.
    - Preserve narrator voice, internal monologue, humor, sarcasm, emotional nuance, and subtext.
    - Preserve dialogue naturally in {target_language} while keeping each speaker's personality, social tone, and implied relationships.
    - Keep names, places, titles, ranks, abilities, organizations, and recurring terminology consistent within the provided text.
    - If a phrase remains ambiguous, choose a natural neutral rendering that preserves the ambiguity; do not resolve it by inventing facts.
    - Do not add explanations, footnotes, translator notes, romanization notes, or commentary unless explicitly requested.
    - Do not repeat the source text.
    - Output only the translation in {target_language}.
    - Preserve image placeholders exactly as-is. Lines like [Image: description] must appear unchanged in the output.
    - Never fabricate or hallucinate content. Do not add events, dialogue, descriptions, or internal thoughts that do not appear in the source.
    - For Japanese, do not invent omitted subjects, objects, pronouns, number, gender, relationships, or speaker identity. When the source leaves one implicit, use neutral English restructuring (including passive or impersonal phrasing) rather than guessing.
    - English may require a grammatical subject, but infer an omitted Japanese subject only when surrounding context establishes it with high confidence; otherwise preserve the ambiguity.
    - Preserve the source order of personal names and do not Westernize, reorder, or silently expand them.
    - Handle honorifics contextually according to the supplied policy; never apply a global suffix or invent a social relationship.
    - Do not invent dialogue attribution, speaker labels, or dialogue tags that are not supported by the source.
    - Preserve Japanese register in character voice: politeness, roughness, authority, age impression, intimacy, distance, keigo, casual or archaic speech, and sentence-ending nuance. Do not turn particles or pronouns into exaggerated gender stereotypes.
    - Restructure clauses within the same paragraph when needed for idiomatic English, while preserving facts, scene order, emphasis, temporal relations, and the distinction between dialogue and narration.
    - Treat onomatopoeia, ellipsis, fragments, punctuation, nested quotations, counters, titles, kinship address, signs, embedded writing, and archaic or fantasy terms according to context. Localize function naturally without adding translator commentary.
    - The glossary block is authoritative. If a source term appears in the glossary, you MUST use its approved translation. Do not substitute synonyms or paraphrases for glossed terms even if they seem contextually reasonable.
    - Pay attention to Japanese honorifics (-san, -kun, -chan, -sama, -sensei, -dono, -sempai, -kohai) and title/rank terms. Follow the honorific policy provided below.
    - The block delimited by `[CONTEXT OVERLAP]` and `[END CONTEXT OVERLAP]` is prior-chunk context, not content to translate. Do not translate, paraphrase, or echo it. Output the [CHAPTER ...] and [P ...] markers only for the paragraphs that come AFTER the [END CONTEXT OVERLAP] line.

    Style requirements:
    - Prioritize accuracy first, then naturalness.
    - Read like a professionally edited {target_language} translation of fiction.
    - Avoid awkward literal phrasing.
    - Keep tense, point of view, and narrative distance consistent with the source.
    - Preserve comedy, drama, and intensity appropriately.
    - For culturally specific references, choose a natural {target_language} rendering that preserves tone and intent without over-explaining.
    """
).strip()


CONTEXT_OVERLAP_PROMPT_BLOCK = (
    "Context overlap: the text above the [END CONTEXT OVERLAP] line is provided "
    "as prior-chunk reference. Do not translate it, do not paraphrase it, and do "
    "not include it in the output. Begin translating from the first [CHAPTER ...] "
    "or [P ...] marker that appears AFTER the [END CONTEXT OVERLAP] line."
)

DEFAULT_USER_PROMPT_TEMPLATE = dedent(
    """
    Translate the following {source_language} fiction text into natural {target_language}.

    Requirements:
    - Keep the same paragraph breaks.
    - Copy every [CHAPTER ...] and [P ...] marker exactly as-is.
    - Include every [P pNNNN] marker exactly once, in source order.
    - If a paragraph body would be blank, keep its [P pNNNN] marker and leave the body blank.
    - Keep names and terminology consistent within this passage.
    - Preserve tone, humor, and narrator voice.
    - Output only the translation.
    - The glossary block is authoritative. If a source term appears in the glossary, use its approved translation.{additional_instructions}

    {source_language} text:
    {text}
    """
).strip()


STRONG_CONSISTENCY_USER_PROMPT_TEMPLATE = dedent(
    """
    Translate the following {source_language} fiction text into natural {target_language}.

    Requirements:
    - Keep the same paragraph breaks.
    - Copy every [CHAPTER ...] and [P ...] marker exactly as-is.
    - Include every [P pNNNN] marker exactly once, in source order.
    - If a paragraph body would be blank, keep its [P pNNNN] marker and leave the body blank.
    - Preserve tone, humor, narrator voice, and character dynamics.
    - Keep names, titles, abilities, and worldbuilding terms consistent with prior established usage.
    - If a recurring term appears, translate it the same way unless context clearly requires otherwise.
    - Output only the translation.
    - The glossary block is authoritative. If a source term appears in the glossary, use its approved translation.{additional_instructions}

    {source_language} text:
    {text}
    """
).strip()


JSON_SYSTEM_PROMPT_TEMPLATE = dedent(
    """
    You are an expert literary translator specializing in fiction.

    Translate the user's {source_language} text into natural {target_language} while preserving meaning, tone, and paragraph structure.

    Rules:
    - Preserve all meaning exactly.
    - Keep paragraph boundaries aligned with the source.
    - Keep names and recurring terms consistent.
    - Do not add commentary.
    - Return one valid JSON object only. No markdown fences or prose outside JSON.
    - Include every source paragraph id exactly once, in source order.
    - Copy paragraph_id values exactly from [P ...] markers.
    - Do not omit the final paragraph id.
    - Include chapter_id when [CHAPTER ...] markers are present.
    - If a paragraph cannot be translated, include its paragraph_map entry with an empty translated_text rather than omitting the paragraph_id.
    - Never fabricate or hallucinate content. Do not add events, dialogue, or descriptions absent from the source.
    - For Japanese, do not invent omitted subjects, objects, pronouns, number, gender, relationships, or speaker identity. Use neutral English restructuring when the source is ambiguous.
    - Preserve source-order names, contextual honorifics, register, and voice. Do not invent dialogue attribution or speaker labels.
    - Preserve Japanese ambiguity and register; sentence/clause restructuring within the same paragraph is allowed when it does not add facts or alter scene order.
    - Translate onomatopoeia, fragments, punctuation, nested quotations, counters, titles, kinship address, signs, embedded writing, and wordplay for their function where natural, without translator commentary.
    - The glossary block is authoritative. If a source term appears in the glossary, you MUST use its approved translation.

    Return this schema:
    {{
      "translated_text": "...",
      "paragraph_map": [
        {{
          "chapter_id": "...",
          "paragraph_id": "...",
          "translated_text": "..."
        }}
      ]
    }}
    """
).strip()


JSON_USER_PROMPT_TEMPLATE = dedent(
    """
    Translate the following {source_language} fiction text into {target_language}.
    The glossary block is authoritative. If a source term appears in the glossary, use its approved translation.{additional_instructions}

    {source_language} text:
    {text}
    """
).strip()


JSON_CONSISTENCY_BLOCK_TEMPLATE = dedent(
    """
    Consistency requirements:
    - Keep recurring names, titles, abilities, and worldbuilding terms consistent with established usage.
    - If a recurring term appears, translate it the same way unless context clearly requires otherwise.
    """
).strip()


STYLE_PRESET_TEMPLATES: dict[str, str] = {
    "fantasy": (
        "Treat fantasy and worldbuilding terminology carefully. Keep magical systems, races, "
        "noble ranks, place names, and invented terms internally consistent and readable in {target_language}."
    ),
    "romance": (
        "Pay close attention to emotional nuance, relationship dynamics, implication, hesitation, "
        "and subtext in dialogue and narration."
    ),
    "action": (
        "Keep action scenes clear, energetic, and easy to follow while preserving pacing, impact, "
        "and spatial clarity in {target_language}."
    ),
    "comedy": (
        "Preserve comedic timing, punchlines, sarcasm, and playful narration naturally in "
        "{target_language} without flattening the humor."
    ),
}

STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES: dict[str, str] = {
    "fantasy": (
        "This is fantasy fiction. Pay special attention to invented terminology, "
        "magical systems, worldbuilding consistency, and noble or rank titles."
    ),
    "romance": (
        "This is romance fiction. Prioritize emotional resonance, relationship dynamics, "
        "subtext, and character voice in dialogue and narration."
    ),
    "action": (
        "This is action fiction. Keep pacing tight, action sequences clear and energetic, "
        "and maintain spatial and logical consistency throughout fight scenes."
    ),
    "comedy": (
        "This is comedy fiction. Preserve comedic timing, wordplay, irony, "
        "and character-driven humor. Do not flatten punchlines or explain jokes."
    ),
}

HONORIFIC_POLICY_BLOCKS: dict[str, str] = {
    "contextual": (
        "Honorific policy: decide contextually. Preserve personal-name honorifics such as -san, -kun, "
        "-chan, and -sama when they carry meaningful social nuance. Localize forms that function as a "
        "rank, profession, royal style, kinship address, or social role when context establishes that "
        "rendering. Use approved glossary terms consistently and never invent a relationship."
    ),
    "retain": (
        "Honorific policy: retain all Japanese honorifics as-is "
        "(-san, -kun, -chan, -sama, -sensei, -dono, -sempai, -kohai, etc.). "
        "Keep them attached to names in their original form."
    ),
    "translate": (
        "Honorific policy: translate Japanese honorifics into natural "
        "target-language equivalents (e.g., Mr., Ms., Dr., Lord, etc.). "
        "Choose equivalents that match the social relationship in context."
    ),
    "omit": (
        "Honorific policy: omit Japanese honorifics from names. Use bare names unless a title is required for clarity."
    ),
}
