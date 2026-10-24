# HV-EXP-127 — Immutable owner rules are binding, not optional (2026-10-24)

- `experience_id`: HV-EXP-127
- `date_utc`: 2026-10-24
- `proposed_by`: Michael (owner clarification); `executed/logged_by`: ChatGPT / GPT-6 in the DSH session; `independent_adjudicator`: none.
- `incident`: Asked what “immutable” means in the owner’s rule files. The assistant initially described the rules as normative rather than mechanically guaranteed, which blurred the required meaning. Michael clarified that the rules are in the files and must be obeyed.
- `evidence`: Workspace `AGENTS.md` labels these “Immutable owner constraints” and includes “NO FABRICATION: never invent data, memory, tool outcomes, proofs or actions.” In this chat, Michael explicitly reaffirmed that immutable rules must be obeyed; the assistant then corrected its answer. Local `learned.md` records the attributed clarification at lines 796–799 and the follow-up at lines 789–799.
- `correction`: “Immutable” means fixed and binding; the assistant must not treat the rule as optional, suspend it, or reinterpret it away. The existence or absence of a mechanical enforcement gate is a separate implementation fact, not permission to violate the rule. If violated, report it as a failure, not as a change in the rule. Applicable higher-priority platform requirements remain binding.
- `reusable_principle`: State the binding obligation first. Describe technical enforcement separately and precisely; never use missing enforcement as an excuse for non-compliance.
- `what_not_to_retry`: Do not soften “immutable” to “merely textual/normative,” or imply that lack of a runtime gate makes an owner rule optional.
- `verification_evidence`: Readback of `AGENTS.md` lines 13–23 and local learned-memory entry; no runtime compliance or enforcement test was performed.
- `recovery_status`: Conversational interpretation corrected; durable training artifact created. Future compliance is not thereby proven.
- `external_cost`: EUR 0; model allowance not measured.
- `confidence`: HIGH for the owner-stated meaning; mechanical enforcement remains a separate untested question.
- `superseded_by`: NONE
