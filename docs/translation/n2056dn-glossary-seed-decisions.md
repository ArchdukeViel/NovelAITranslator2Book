# N2056DN Glossary Seed Decisions

## 1. Purpose

This is the initial seed decision sheet for N2056DN glossary consistency. It
turns the known chapter 1-7 terminology drift into practical owner/admin review
items that can later become approved per-novel glossary entries.

This document does not implement the glossary system. It does not create schema,
migrations, backend services, admin UI, prompt injection, QA checks, or repair
logic.

These decisions are intended to become approved per-novel glossary entries after
owner/admin review. Uncertain terms remain owner/admin decisions and must not be
silently invented or treated as approved.

## 2. Novel Identity

| Field | Value |
|---|---|
| Source | Syosetu |
| Source ID | `n2056dn` |
| Platform novel identity | `n2056dn` |
| Public slug | `my-father-is-a-hero-my-mother-is-a-spirit-and-i-am-a-reincarnator` |
| Source title | `çˆ¶ã¯è‹±é›„ã€æ¯ã¯ç²¾éœŠã€å¨˜ã®ç§ã¯è»¢ç”Ÿè€…ã€‚` |
| Translated title | `My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator.` |
| Current translated chapter range | Chapters 1-7 |
| Chapter 8 status | Unavailable |

## 3. Decision Status Legend

| Status | Meaning |
|---|---|
| `APPROVED` | Owner/admin has explicitly accepted this canonical form. No terms are marked approved in this phase unless already explicit. |
| `RECOMMENDED` | Available audit evidence supports this as the safest seed candidate, but owner/admin can still override before implementation. |
| `NEEDS_OWNER_DECISION` | Current evidence is insufficient or the term affects story/worldbuilding enough that owner/admin must decide. |
| `REJECTED_ALIAS` | Alias should be treated as banned for a specific canonical term once that term is approved or recommended. |
| `DEPRECATED` | Older rendering should be phased out but may need context-aware repair rather than automatic replacement. |

## 4. Conservative Decision Rules

- If one spelling is clearly dominant and likely intentional from the audit
  evidence, mark it `RECOMMENDED`.
- If the audit clearly identifies one spelling as wrong, mark it
  `REJECTED_ALIAS` or `DEPRECATED`.
- If the term cannot be confidently decided from available evidence, mark it
  `NEEDS_OWNER_DECISION`.
- Do not pretend uncertain noble ranks, family names, or organization names are
  solved.
- Do not invent Japanese source terms if not visible in the available docs or
  files.
- Do not treat this document as permission to rewrite existing chapters.

## 5. Canonical Seed Glossary Table

| Concept / Japanese source term if known | Term type | Canonical English | Allowed aliases | Rejected/banned aliases | Status | Reason | Evidence / observed drift | Notes for prompt injection |
|---|---|---|---|---|---|---|---|---|
| House/family name, source term recorded in audit as `ãƒ´ã‚¡ãƒ³ã‚¯ãƒ©ã‚¤ãƒ•ãƒˆ` | `family_house` | Needs owner choice: `Vancleift` or `Vanclyft` are the leading candidates | None until owner choice | `Vancroft`; `Vancraft` should be banned after canonical choice | `NEEDS_OWNER_DECISION` | The audit rates the proposed house romanization low-medium confidence. `Vancroft` is frequent in current text but least faithful to the source sound; `Vancleift` is an existing variant; `Vanclyft` was proposed for source fidelity. | `Vancleift` / `Vancroft` / `Vancraft` drift appears in chapters 4, 5, and 7. | Do not enforce yet. Future prompt should include the owner-approved house spelling and explicitly avoid the other variants. |
| Attendant name, source term recorded in audit as `ã‚¢ãƒ«ãƒ™ãƒ«ãƒˆ` | `character` | `Albert` | None needed initially | `Alberto` | `RECOMMENDED` | `Albert` is more natural in English fantasy naming and appears more widely; audit recommends owner decision but points to `Albert` as the practical seed. | `Albert` / `Alberto` drift appears in chapters 4-7. Narrow local count found both forms, with `Albert` more frequent. | Enforce `Albert`; flag `Alberto` as a banned alias. |
| Formal mother/spirit name, source term recorded in audit as `ã‚ªãƒªã‚¸ãƒ³` | `character` / `divine_name` | `Origin` | Title phrases may vary only when translating full titles | None for the personal/formal name | `RECOMMENDED` | Audit confidence is high for `Origin` as the personal/formal name. | `Origin` appears across chapters 1, 2, 5, and 6; title renderings also vary. | Enforce `Origin` for the personal/formal name. Do not force every title phrase to exactly `Origin`. |
| Mother/spirit nickname, source term recorded in audit as `ã‚ªãƒ¼ãƒª` | `character` / `nickname` | `Ori` | None initially | `Auri` | `RECOMMENDED` | `Ori` aligns with `Origin`; audit identifies `Auri` as one-off drift. | `Ori` / `Auri` drift appears in chapters 6-7. | Enforce `Ori`; flag `Auri` as a banned alias after owner confirmation. |
| Spirit realm, source term recorded in audit as `ç²¾éœŠç•Œ` | `place` | `Spirit Realm` | None initially | `Spirit World` when source is `ç²¾éœŠç•Œ` | `RECOMMENDED` | Audit confidence is high for `Spirit Realm` and says `world` should be reserved for generic wording. | `Spirit Realm` / `Spirit World` drift appears across chapters 1-7. | Enforce `Spirit Realm` for `ç²¾éœŠç•Œ`; QA should distinguish this from `ç²¾éœŠå›½`. |
| Spirit country/polity, source term recorded in audit as `ç²¾éœŠå›½` | `place` / `polity` | Needs owner choice, likely `Spirit Kingdom` if distinct from `ç²¾éœŠç•Œ` | None yet | Do not blanket-ban `Spirit Realm` until source context is checked | `NEEDS_OWNER_DECISION` | Audit says this appears distinct from Spirit Realm but needs human decision. | Source occurrences noted around chapters 4-5; current English may blur it with `Spirit Realm`. | Do not enforce yet. Future prompt may include an unresolved note to check source context. |
| Noble title, source term recorded in audit as `ä¾¯çˆµ` | `title` / `rank` | `marquess` | `marquis` only if owner chooses style later | `duke`; `Duke` when source is `ä¾¯çˆµ` | `RECOMMENDED` | Audit confidence is high that `ä¾¯çˆµ` is marquess/marquis, not duke. | Drift includes `Duke`, `duke`, `marquess`, `Marquisate`, and house phrasing. | Enforce `marquess` for the rank/title when source is `ä¾¯çˆµ`; QA should be source-aware. |
| Noble house, source term recorded in audit as `ä¾¯çˆµå®¶` | `family_house` / `title` | Needs owner choice after house name decision | `House {approved family name}` is the likely formal style | `Ducal House` unless source is `å…¬çˆµ`; raw family variants tied to rejected house spelling | `NEEDS_OWNER_DECISION` | House style depends on the unresolved family spelling and exact noble rank context. | Drift includes `Vancleift Ducal House`, `Vancroft family`, `Vancraft family`, and marquess-house renderings. | Do not enforce until the family spelling is decided. Future prompt should separate family name from rank/title. |
| Noble title, source term recorded in audit as `å…¬çˆµ` | `title` / `rank` | `duke` | `ducal` only for adjectival context | `marquess` when source is `å…¬çˆµ` | `RECOMMENDED` | Audit notes `å…¬çˆµ` should use duke/ducal, while `ä¾¯çˆµ` should not. | Current output mixes `Dukedom`, `Duke`, `Ducal House`, and `marquess` vocabulary. | Enforce only with source-term awareness; do not globally replace noble words. |
| Knight organization, source term recorded in audit as `é¨Žå£«å›£` | `organization` | `Order of Knights` | None initially | `Kingdom Knights` unless owner later chooses it as formal name | `RECOMMENDED` | Audit prefers `Order of Knights` unless later chapters reveal a formal organization name. | `Kingdom Knights` / `Order of Knights` drift appears in chapters 1 and 5. | Enforce `Order of Knights`; flag `Kingdom Knights` as a warning/banned alias depending owner policy. |
| Protagonist name, source term recorded in audit as `ã‚¨ãƒ¬ãƒ³` | `character` | Needs owner choice: `Ellen` vs `Eren` | None until owner choice | Neither spelling should be banned until owner choice | `NEEDS_OWNER_DECISION` | Existing public text mostly uses `Ellen`, but the audit warns the source katakana can support either. | `Ellen` / `Eren` drift appears in chapters 2-5 and 7, with `Eren` observed at least once. | Do not enforce yet. Prompt can mention unresolved protagonist-name decision only as non-binding context. |

## 6. Initial Recommended Decisions

Recommended seed entries, subject to owner/admin approval:

- Use `Albert` for `ã‚¢ãƒ«ãƒ™ãƒ«ãƒˆ`; reject `Alberto`.
- Use `Origin` for the formal mother/spirit personal name `ã‚ªãƒªã‚¸ãƒ³`.
- Use `Ori` for the nickname `ã‚ªãƒ¼ãƒª`; reject `Auri`.
- Use `Spirit Realm` for `ç²¾éœŠç•Œ`; reject `Spirit World` only when the
  source term is specifically `ç²¾éœŠç•Œ`.
- Use `marquess` for `ä¾¯çˆµ`; reject `duke` for that source term.
- Use `duke` / contextual `ducal` for `å…¬çˆµ`; do not confuse this with
  `ä¾¯çˆµ`.
- Use `Order of Knights` for `é¨Žå£«å›£`; reject or at least warn on
  `Kingdom Knights`.

Not yet decided:

- Family/house spelling for `ãƒ´ã‚¡ãƒ³ã‚¯ãƒ©ã‚¤ãƒ•ãƒˆ`.
- Formal house style for `ä¾¯çˆµå®¶`.
- Whether `ç²¾éœŠå›½` should be `Spirit Kingdom`.
- Whether protagonist name should be `Ellen` or `Eren`.

## 7. Prompt Injection Seed

Compact draft for future translation prompts. This block includes only
`RECOMMENDED` terms. It excludes unresolved terms as enforceable constraints.

```text
N2056DN glossary constraints:
- ã‚¢ãƒ«ãƒ™ãƒ«ãƒˆ => Albert. Do not use Alberto.
- ã‚ªãƒªã‚¸ãƒ³ => Origin when used as the personal/formal spirit name.
- ã‚ªãƒ¼ãƒª => Ori. Do not use Auri.
- ç²¾éœŠç•Œ => Spirit Realm. Do not use Spirit World for this source term.
- ä¾¯çˆµ => marquess. Do not translate this source term as duke.
- å…¬çˆµ => duke; use ducal only as an adjective when context requires it.
- é¨Žå£«å›£ => Order of Knights. Do not use Kingdom Knights.

Unresolved, do not enforce yet:
- ãƒ´ã‚¡ãƒ³ã‚¯ãƒ©ã‚¤ãƒ•ãƒˆ family/house spelling is pending owner decision.
- ã‚¨ãƒ¬ãƒ³ protagonist name is pending owner decision: Ellen vs Eren.
- ç²¾éœŠå›½ polity/place rendering is pending owner decision.
```

## 8. QA Rules Seed

Future N2056DN glossary QA should:

- Flag banned aliases such as `Alberto`, `Auri`, source-aware misuse of `Spirit
  World`, `duke` for `ä¾¯çˆµ`, and `Kingdom Knights`.
- Flag inconsistent character names, especially `Albert` / `Alberto`, `Ori` /
  `Auri`, and the unresolved `Ellen` / `Eren` pair.
- Flag inconsistent noble-rank rendering, but only with source-term awareness.
- Flag inconsistent organization and place rendering for `Order of Knights`,
  `Spirit Realm`, and possible `Spirit Kingdom`.
- Treat locked owner-approved violations as hard errors after approval.
- Treat unresolved terms and likely false positives as warnings until owner/admin
  decisions and source-aware matching exist.

## 9. Existing Chapter Repair Notes

Existing chapters 1-7 should not be globally find/replaced.

Any repair pass must be previewed and audited. Names, noble titles, family/house
phrasing, organizations, and places require context-aware replacement. Noble
terms are especially risky because `ä¾¯çˆµ` and `å…¬çˆµ` require different English
renderings even though current English output mixes rank words.

Repair should happen only after glossary backend/QA support or a dedicated
controlled manual repair phase. A repair phase should preserve paragraph markers,
reader layout, active translation version behavior, and public chapter contracts.

## 10. Human Decisions Still Needed

- Choose canonical house/family spelling for
  `ãƒ´ã‚¡ãƒ³ã‚¯ãƒ©ã‚¤ãƒ•ãƒˆ`: likely `Vancleift` or `Vanclyft`; reject
  `Vancroft` and `Vancraft` only after choosing the canonical form.
- Choose noble house style for `ä¾¯çˆµå®¶`, likely `House {approved family name}`
  in formal contexts and `{approved family name} family` in casual narration.
- Decide whether `ç²¾éœŠå›½` should be `Spirit Kingdom` and how it differs from
  `ç²¾éœŠç•Œ` / `Spirit Realm`.
- Decide protagonist name: `Ellen` or `Eren`.
- Decide whether `Order of Knights` is final or merely the best current
  placeholder until a formal organization name appears later.
- Decide whether glossary QA should block publishing immediately for
  `RECOMMENDED` terms or only after owner/admin marks terms `APPROVED`.

## 11. Recommended Next Phase

Recommended next phase:

`GLOSSARY-KAKUYOMU-SEED-AUDIT-1`

Run the Kakuyomu seed audit before backend schema implementation because the
project already has a saved Kakuyomu novel and the glossary system must remain
source-agnostic.
