<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Architecture
- Shared visual roles are defined in `src/styles.css`; clinical documents use unframed sections and dividers so presentation stays consistent without changing clinical rules.
- All synthetic data lives in `src/mockData.ts` and is read through `src/api.ts` (mirrors FastAPI endpoints) so a real backend can replace it without touching UI.
- EHDS decision order and small-cell formatting live in `src/lib/rules.ts` with tests in `src/test/rules.test.ts`; keep UI free of rule logic.
- Cross-page demo state (access log, opt-out, guided tour) lives in `src/lib/app-state.tsx` context; no persistence by design.
- Primary-use UI lives in `src/components/primary/*`; the route switches clinical tabs and cross-border steps via search params, while technical conversions remain backend-only.
- Primary-use access rules (`decideAccess`) live in `src/lib/rules.ts` and HL7 v2 → FHIR mapping in `src/lib/hl7.ts`, both tested in `src/test/primary.test.ts`; UI only renders their output.
- Preset synthetic identities use the in-memory DemoSessionProvider and presentation-only role boundaries in role-rules; they are not real authentication, and FastAPI must independently authenticate and authorize live requests before production.
- Clinical version state, superseded signed documents, applications and hospital provision state live in AppStateProvider for the demo; never persist synthetic sessions or private state to browser storage.
- Demo session and app-state context identities survive development refresh through Vite hot data so refreshed consumers still match mounted providers; no user or clinical state is stored there.
- All new data calls use the FastAPI adapter with labelled synthetic fallbacks only for unavailable services; access refusals and rejected live writes must not silently succeed.
- Clinical signing/required-section rules and identity validation live in tested pure rule modules; UI cannot override clinical release gates.
- KIS letter creation uses the API adapter and a tested local synthetic assembler; never issue patient-level AI calls, overwrite edited/signed drafts, or disguise simulation as live AI.
- Interested-party components receive only current-account evaluations and minimized public catalogue/register DTOs; never reuse staff result or patient components there.

- Cross-border summaries use a dedicated release adapter and tested response minimisation before rendering; re-evaluate saved consent and identity per release and audit only returned sections.
