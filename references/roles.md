# Roles and two-way model fallback

Use the starting provider's column; do not make every worker inherit the coordinator's model. Explicit user choices override project `CLAUDE.md` preferences, which override these defaults. These are task-fit defaults, not guarantees of equal model quality. Check route availability and supported effort before dispatch.

## Lookup table

`openai-codex` = existing ChatGPT/Codex connection; `anthropic` = existing Claude connection. “Claude-first” includes starting with Opus: use the Claude column's role-specific models, not Opus for every job. Switch columns for the same role when the starting provider is exhausted.

| Role | Codex model · effort | Claude model · effort |
|---|---|---|
| Coordinator: sectioning, shared brief, consistency | `gpt-6.1-sol` · high | `claude-opus-5-5` · high |
| Digester: straightforward slide/diagram extraction | `gpt-6-luna` · low | `claude-haiku-5-5` · low |
| Section planner: notes, verified trace, storyboard, script | `gpt-6.1-sol` · high | `claude-opus-5-5` · high |
| Difficult trace / failed-check escalation | `gpt-6-astra` · high | `claude-opus-5-5` · high |
| Optional narration polish | `gpt-6.1-sol` · high | `claude-sonnet-5-5` · high |
| Animator: code, layout, draft fixes | `gpt-6.1-sol` · high | `claude-sonnet-5-5` · high |
| Simple animation pilot, not the general default | `gpt-6.1-terra` · high | `claude-sonnet-5-5` · medium |
| Independent visual reviewer | `gpt-6.1-terra` · medium | `claude-sonnet-5-5` · medium |
| Speech triage / clerk: bounded classification and approved edits | `gpt-6-luna` · low | `claude-haiku-5-5` · low |
| Semantic, numerical or ambiguous speech fix | `gpt-6.1-sol` · high | `claude-sonnet-5-5` · high |
| Extraction, lint, TTS, rendering, assembly, hashes | Local scripts; no LLM | Local scripts; no LLM |

Use a vision-capable route for digesting/review; escalate ambiguous diagrams and `[verify]` values. If Haiku 5.5 is unavailable, Haiku 4.5 with provider-native defaults is a legacy alternative; do not assume its API accepts the same effort parameter. Raise effort or use the difficult-trace row only for a concrete unresolved problem, not every section.

## Ownership and checks

- One planner owns `notes.md`, `lesson.yaml`, `script.md`; one animator owns `scenes.py` and its draft loop. Coordinator owns shared files; reviewer is read-only; clerk packages validated outputs. No concurrent writers to one section.
- Default to one section planner, including narration. Add an independent trace verifier or prose polish only when needed; a short lesson may combine planning and animation.
- Complete the deck digest before planning. Verify uncertain source diagrams and rederive calculations with tools before they enter speech or animation.
- Freeze `script.md` after block-length checks. Animator copies speech verbatim; planner/coordinator approves edits or natural-boundary splits. Update script/code together, preserve beats/bookmarks, rerun script lint and affected media checks. `beats:` is metadata after all speech in its block.
- Normalize obvious ASR formatting with scripts. A cheap model may triage flags or apply approved replacements; escalate changed bits, symbols, negation, recipient relationships or uncertain meaning. ASR is not a listening check.

## Fallback and resumption

1. Persist the active provider family and completed artifacts in checkpoints. Reuse the table in either direction: Codex → Claude or Claude → Codex. User provider restrictions still apply.
2. On an explicit quota/credit exhaustion, skip repeated probes and switch to the other column using existing authorized credentials. Record the exhausted provider to prevent ping-pong. A transient network/server failure gets at most one retry; respect a short retry-after when supplied.
3. Resume the unfinished stage from its files and validated checkpoint, not from an empty scaffold. Save runnable work early. Never replace valid completed stages because the provider changed.
4. If a cheap role fails a content/quality check, escalate within its current family. If a strong role's repair still fails, checkpoint `blocked` with evidence. If both providers are exhausted, save reset times and stop; never enable a new paid route or buy credits automatically. A short probe proves access, not remaining quota or sustained reliability.

## Routing and records

This is orchestration policy, not a runtime failover engine. If the coordinator itself cannot make another model call, the harness/user must switch it or use an already configured runtime fallback, then resume.

Use the live delegation schema. With supported per-task model/route controls, pin provider, model and effort explicitly. In Hermes `model_map`/`profile_routes`, configured routes govern children; `delegation.model`/`provider` do not override them. Do not install or change a delegation backend implicitly.

With the default Hermes backend, save `delegation.model`, `delegation.provider`, `delegation.reasoning_effort`; set them with `hermes config set`, read back, then dispatch a same-route batch. These settings are profile-wide: serialize setting/dispatch changes; do not race other sessions. Restore temporary overrides after the stage unless a later user instruction supersedes them. Never assume a model name alone sets effort.

Keep legacy `roles: {planner: <model>, animator: <model>}` fields; append `stage_runs` records with `stage`, actual `provider`, `model`, `reasoning_effort`, and `outcome` (success/quota/failed/interrupted). Record unavailable routing data as unknown, not inferred. Keep previous attempts, artifact paths and failure evidence; record deck digestion at collection scope. Scripts have no agent model; record TTS engine/preset separately.

Do not assume API prices convert into subscription quota. Keep routing instructions focused on task suitability. See [parallel-sections.md](parallel-sections.md) for locks, stage boundaries and assembly; section workers receive [worker-card.md](worker-card.md), their role/route and brief, not this whole policy.
