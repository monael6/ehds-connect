# Role-based EHDS restructuring

- [x] Refine the shared design and clinical workspace for a cleaner blue-and-white presentation without changing content or clinical behaviour.
- [x] Verify the refreshed design, navigation and letter creation on desktop and narrow screens; five targeted tests passed, no horizontal overflow at 922px or 390px, and no runtime errors in the signed-in walkthrough.

- [x] Prevent context identity mismatch during preview refresh; provider lifecycle/routing tests passed and signed-in navigation after provider updates verified without runtime errors.

- [x] Translate discharge letters into English and restore explicitly simulated KIS-based AI draft creation with clinical safeguards.
- [x] Remove Novak's role switch and treatment-access history from My data rights.
- [x] Test the requested changes and check the demo flows; 28 tests passed, English draft/signing and HDAB/rights views verified without runtime errors.

- [x] User chose preset demo accounts without stored profiles.
- [x] Add preset demo sign-in, role-aware navigation, denied-area views, own activity log and sign-out.
- [x] Wire FastAPI adapters with labelled synthetic fallbacks; preserve decision logic and conversions.
- [x] Simplify hospital patient list and summary; remove technical/rule views.
- [x] Rebuild ELGA discharge sections, source panels, editing reasons/history, sign-off and corrections.
- [x] Update guided cross-border identity, saved consent, restricted release and emergency flow.
- [x] Preserve HDAB tools, add permit criteria/actions and global audit filters.
- [x] Build approved hospital requests/catalogue management and restricted public/researcher applications.
- [x] Verify demo roles, clinical safeguards, signed letter/send, hospital provision, own applications, cross-border and HDAB action flows; 33 tests passed.
- [ ] Verify live FastAPI responses, permanent audit storage and server-side authorization. Blocked: service at localhost:8000 is unavailable; preset demo identities are not real authentication.