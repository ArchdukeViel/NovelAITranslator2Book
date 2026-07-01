# n2056dn Term Consistency Audit

## Summary

Audit target: Syosetu `n2056dn`, public title `My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator.`

Coverage audited: translated chapters 1-7.

Verdict: the currently published chapters are readable, but the translation shows material term drift around the noble house name, one attendant name, the mother/spirit name, the spirit realm, and noble-title vocabulary. These should be fixed through a canonical novel glossary before translating more chapters.

No chapter text was rewritten in this audit.

## Current Translated Coverage

| Field | State |
|---|---|
| Source novel ID | `n2056dn` |
| Public slug | `my-father-is-a-hero-my-mother-is-a-spirit-and-i-am-a-reincarnator` |
| Chapter count | 148 |
| Public translated chapters | 1-7 |
| Latest public chapter | 7 |
| Next unavailable chapter | 8 |
| Public marker leakage | None found in chapters 1-7 |

## High-Priority Inconsistencies

1. **House/family name drift**
   - Source term: `ヴァンクライフト`
   - Observed variants: `Vancleift`, `Vancroft`, `Vancraft`
   - Chapters: 4, 5, 7
   - Risk: high. This is a recurring house/family identifier and should be stable.

2. **Attendant name drift**
   - Source term: `アルベルト`
   - Observed variants: `Albert`, `Alberto`
   - Chapters: 4, 5, 6, 7
   - Risk: high. Same character appears under two English names.

3. **Mother/spirit familiar-name drift**
   - Source terms: `オリジン`, `オーリ`
   - Observed variants: `Origin`, `Ori`, `Auri`
   - Chapters: 1, 2, 5, 6, 7
   - Risk: high. The formal name and nickname should be separated and stable.

4. **Spirit realm / spirit country drift**
   - Source terms: `精霊界`, `精霊国`
   - Observed variants: `Spirit Realm`, `Spirit World`, `Spirit Realm` for possibly different source terms
   - Chapters: 1, 2, 3, 4, 5, 6, 7
   - Risk: medium-high. The setting language should distinguish realm/world/country if the source does.

5. **Noble-rank and house-title drift**
   - Source terms include `侯爵`, `公爵`, `侯爵家`
   - Observed variants: `Dukedom`, `Ducal House`, `Duke`, `Marquisate`, `marquess family`, `house of marquesses`
   - Chapters: 1, 4, 5
   - Risk: high. Rank errors change worldbuilding meaning.

6. **Knight organization drift**
   - Source term: `騎士団`
   - Observed variants: `Kingdom Knights`, `Order of Knights`
   - Chapters: 1, 5
   - Risk: medium. Both are understandable, but the organization should have one canonical English name.

## Proposed Canonical Glossary

| Source term | Romaji / reading | Category | Canonical English | Observed variants | Chapters observed | Confidence | Notes |
|---|---|---|---|---|---|---|---|
| エレン | Eren / Ellen | Character | Ellen | `Ellen`, `Eren` | EN: 2, 3, 4, 5, 7 / JP: 2, 3, 4, 5, 7 | Medium | Existing public title/chapter text mostly uses `Ellen`; chapter 5 has one `Eren`. Human approval recommended because source katakana can support either. |
| ロヴェル | Roveru | Character | Lovell | `Lovell`, `Lord Lovell`, `Lovell-sama` | 1, 3, 4, 5, 6, 7 | High | Keep `Lovell`; render honorifics by context, usually `Lord Lovell` in formal address and `Lovell` in narration. Avoid leaving `-sama` unless style guide allows it. |
| アルベルト | Aruberuto | Character | Albert | `Albert`, `Alberto` | EN: 4, 5, 6, 7 / JP: 4, 5, 6, 7 | Medium | `Alberto` may be phonetically closer; `Albert` already appears more widely. Needs human decision before repair. |
| オリジン | Origin | Divine/spirit name | Origin | `Origin`, `Queen of Primordial Spirits`, `Mother of All` | EN: 1, 2, 5, 6 / JP: 1, 2, 5, 6 | High | Use `Origin` as the personal/formal name. Titles can vary only when translating title phrases. |
| オーリ | Oori | Nickname | Ori | `Ori`, `Auri` | EN: 6, 7 / JP: 6, 7 | Medium | `Ori` aligns better with `Origin`; `Auri` appears once as drift. Human approval recommended. |
| ヴァンクライフト | Vankuraifuto | Family / house | Vanclyft | `Vancleift`, `Vancroft`, `Vancraft` | EN: 4, 5, 7 / JP: 4, 5, 7 | Low-Medium | Needs human decision. `Vanclyft` is a proposed romanization from the source sound; `Vancleift` is closest to one existing machine variant; `Vancroft` is most frequent in current EN but least faithful to the source. |
| 侯爵 | koushaku | Noble title | marquess | `Duke`, `duke`, `marquess`, `house of marquesses` | EN: 1, 5 / JP: 1, 5 | High | `侯爵` is marquess/marquis, not duke. Prefer `marquess` for the title and `marquess house` / `House X` for the family. |
| 侯爵家 | koushaku-ke | Noble house | marquess house / House Vanclyft | `Vancleift Ducal House`, `Vancroft family`, `Vancraft family` | EN: 4, 5, 7 / JP: 5 | High | Avoid `ducal` unless the source is `公爵`. Prefer `House {family name}` in narration once the family romanization is approved. |
| 公爵 | koushaku | Noble title | duke | `Dukedom`, `Duke`, `ducal` | EN: 1, 4 / JP: 1, 4 | Medium | Japanese `公爵` and `侯爵` are both romanized `koushaku`; source characters must be checked. Keep `duke/ducal` only for `公爵`. |
| 騎士団 | kishidan | Organization | Order of Knights | `Kingdom Knights`, `Order of Knights` | EN: 1, 5 / JP: 1, 5 | Medium-High | Prefer `Order of Knights` unless later chapters identify a formal order name. |
| 団長 | danchou | Rank/title | commander | `commander`, `commander of the Order of Knights` | 1, 5 | High | Stable enough; keep lower-case when used as a role, title-case when formal. |
| 副隊長補佐 | fukutaichou hosa | Rank/title | assistant vice-commander | `vice-commander assistant` | 1, 5 | Medium | Awkward but understandable. Needs style decision if this rank recurs. |
| 精霊王 | seirei-ou | World term / title | Spirit King | `Spirit King` | 1, 2, 4, 5 | High | Current output is stable. |
| 元始の女王 | genshi no joou | Divine/spirit title | Primordial Queen | `Primeval Queen`, `Queen of Primordial Spirits` | 2, 5 | Medium | Prefer `Primordial Queen` for compact consistency. Human approval recommended. |
| 精霊界 | seireikai | Place | Spirit Realm | `Spirit Realm`, `Spirit World` | EN: 1, 2, 3, 4, 6, 7 / JP: 1, 2, 3, 5, 6, 7 | High | Prefer `Spirit Realm` and reserve `world` for generic wording only. |
| 精霊国 | seireikoku | Place / polity | Spirit Kingdom | `Spirit Realm` / unclear | JP: 4, 5 | Medium | This appears distinct from `精霊界`; needs human decision. |
| モンスターテンペスト | Monsutaa Tenpesuto | Event | Monster Tempest | `Monster Tempest` | 1, 4, 5, 6, 7 | High | Current output is stable. |
| テンバール | Tenbaaru | Country | Tembar Kingdom | `Tembar Kingdom` | 1, 5 | Medium | Current output appears stable; spelling could be `Tembarl`/`Tembar` depending style preference. |
| アギエル | Agieru | Character | Agiel | `Agiel`, `Agiel-sama` | 5, 7 | High | Keep `Agiel`; render honorifics by context, usually without `-sama` in narration. |
| サウヴェル | Sauveru | Character | Sauvell | `Sauvell`, `Sauvell-sama` | 4, 5 | Medium | Current base name is stable enough; approve spelling before repair. |
| 教会 | kyoukai | Place / institution | church | `church` | 6, 7 | High | Stable enough. |
| 女神 | megami | Divine term | goddess | `Goddess`, `Goddesses` | 6 | High | Stable enough; formal names need later confirmation. |
| ヴォール / ヴァール | Vooru / Vaaru | Divine names | Vohl / Vahl | `Vohl`, `Vahl` | 6 | Low-Medium | Needs human decision; current output is plausible but should be approved before recurring use. |

## Terms Needing Human Decision

| Decision | Options | Recommendation |
|---|---|---|
| House name for `ヴァンクライフト` | Vanclyft / Vancleift / Vancroft / Vancraft | Choose one before repair. I recommend `Vanclyft` for source fidelity, or `Vancleift` if preserving a current machine variant is preferred. |
| `アルベルト` English name | Albert / Alberto | Choose based on desired localization style. I recommend `Albert` for natural English fantasy naming and because it is already most common. |
| Protagonist name `エレン` | Ellen / Eren | Existing public text mostly uses `Ellen`; approve `Ellen` unless source/author romanization says otherwise. |
| `オーリ` nickname | Ori / Auri | Recommend `Ori`, because it clearly derives from `Origin`. |
| `元始の女王` title | Primordial Queen / Primeval Queen / Queen of Primordial Spirits | Recommend `Primordial Queen`; use `Origin, the Primordial Queen` on first mention. |
| `精霊国` vs `精霊界` | Spirit Kingdom vs Spirit Realm | Keep `Spirit Realm` for `精霊界`; decide whether `精霊国` should be `Spirit Kingdom`. |
| Noble house style | House Vanclyft / Vanclyft family / Vanclyft Marquess House | Recommend `House Vanclyft` for formal references and `the Vanclyft family` in casual narration. |

## Recommended Canon for Immediate Future Translation

Use this glossary injection before translating chapter 8:

| Source term | Canonical English |
|---|---|
| エレン | Ellen |
| ロヴェル | Lovell |
| アルベルト | Albert |
| オリジン | Origin |
| オーリ | Ori |
| ヴァンクライフト | Vanclyft or approved alternative |
| 侯爵 | marquess |
| 侯爵家 | House Vanclyft / marquess house |
| 公爵 | duke |
| 騎士団 | Order of Knights |
| 団長 | commander |
| 副隊長補佐 | assistant vice-commander |
| 精霊王 | Spirit King |
| 元始の女王 | Primordial Queen |
| 精霊界 | Spirit Realm |
| 精霊国 | Spirit Kingdom, pending approval |
| モンスターテンペスト | Monster Tempest |
| テンバール王国 | Tembar Kingdom |
| アギエル | Agiel |
| サウヴェル | Sauvell |

## Repair Candidates for Existing Chapters

Do not patch chapter text until the glossary is approved. When approved, likely repair rules include:

- `Vancleift`, `Vancroft`, `Vancraft` -> approved house name.
- `Alberto` -> approved `Albert` / `Alberto`.
- `Auri` -> approved `Ori` / `Auri`.
- `Spirit World` -> `Spirit Realm` when source is `精霊界`.
- `Dukedom`, `Ducal House`, `Duke` -> only keep when source is `公爵`; otherwise repair to `marquess` / `House {name}`.
- `Kingdom Knights` -> `Order of Knights`.
- `Primeval Queen`, `Queen of Primordial Spirits` -> approved title, likely `Primordial Queen`.
- `Eren` -> approved `Ellen` / `Eren`.

## Recommendations for Future Pipeline

1. Add a novel-specific glossary injection before translating chapter 8.
2. Add glossary QA after translation to flag unapproved variants.
3. Add a glossary repair phase for chapters 1-7 after human approval.
4. Track source term, canonical English, and allowed variants separately.
5. Later public-reader feature: glossary popovers for major names/titles.
6. Later admin feature: owner-managed per-novel glossary overrides before a batch run.

## Source-Agnostic Design Notes

This audit uses Syosetu `n2056dn` as the pilot case, but the glossary system should be source-agnostic.

- Glossary entries should be scoped per novel, not per source site. A novel can move sources, be mirrored, or have metadata reconciled without changing its canonical terminology.
- Source-specific adapters may help discover source terms, ruby/furigana, readings, and source metadata, but they should not own the canonical English glossary.
- Canonical glossary storage, prompt injection, post-translation glossary QA, reader glossary popovers, and future user/owner overrides should work for Syosetu, Kakuyomu, Novel18, generic sources, and future source adapters.
- Avoid naming future models, routes, services, or classes as Syosetu-only unless they are truly parser-specific. Prefer names such as `NovelGlossary`, `GlossaryEntry`, `GlossaryQA`, or `SourceTermCandidate` over source-bound names.

## Audit Method

- Checked public API state for detail and chapters 1-8.
- Read local stored translated text for chapters 1-7.
- Read local stored raw source text for chapters 1-7 only to identify source terms.
- Counted observed English variants by chapter.
- Mapped high-confidence source terms from stored raw text.
- Did not call providers, translate, scrape, or rewrite translated chapter text.
