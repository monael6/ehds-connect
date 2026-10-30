"""Permit criteria checklist (Art. 68) shown to HDAB staff and used by the eligibility wizard.

Each item is "yes", "no" or "check" (to be checked by staff) with a short reason.
The automatic decision (decision.py) is never overridden here; the checklist explains it
and lists what a human still has to verify.
"""
from __future__ import annotations

import re

from .decision import APPROVE_SPE, APPROVE_STATISTICAL, REJECT, Decision, collect_text

# Art. 53(1) purposes, with words that point to them
PURPOSES_53 = [
    ("a", "public interest in public and occupational health", r"public health|prevention|surveillance|occupational health|epidemiolog"),
    ("b", "policy-making and regulatory activities", r"policy|ministry|regulator|quality programme|quality of care|treatment gap|plan(ning)? (a )?(quality|prevention)"),
    ("c", "statistics (official statistics)", r"official statistic|statistics office|annual (health )?report|national statistic"),
    ("d", "education or teaching in health or care", r"teach|education|training module|curricul|course"),
    ("e", "scientific research related to health or care", r"research|study|studies|investigat|analy[sz]e|risk factor|compare"),
    ("e", "development and innovation of products/services, training and testing of algorithms",
     r"train\w*|algorithm|model|prediction|machine learning|ai\b|software|innovation|medical device"),
    ("f", "improvement of the delivery of care / personalised care", r"improv\w* (care|treatment|delivery)|personali[sz]ed|intervene earlier|clinical decision"),
]

QUALIFIED_ORG = r"universit|institut|research|ministry|federal|statistic|hospital|klinik|cancer cent|centre|center|academ|agency|authority|public health|spin-off"


def _status(ok: bool | None) -> str:
    return "check" if ok is None else ("yes" if ok else "no")


def purposes(text: str) -> list[dict]:
    out, seen = [], set()
    for letter, label, pat in PURPOSES_53:
        if re.search(pat, text, re.I) and label not in seen:
            seen.add(label)
            out.append({"article": f"53(1)({letter})", "purpose": label})
    return out


def checklist(request: dict, decision: Decision) -> list[dict]:
    text = "\n".join(collect_text(request))
    org = str((request.get("applicant") or {}).get("organisation", "")) if isinstance(request.get("applicant"), dict) else str(request.get("applicant", ""))
    found = purposes(text)
    records = decision.decision == APPROVE_SPE
    asked_records = "application" in str(request.get("requested_as", "")).lower()
    items = []

    prohibited = decision.decision == REJECT
    items.append({"id": "art54", "label": "Not a prohibited purpose (Art. 54)", "status": _status(not prohibited),
                  "reason": ("Prohibited: " + "; ".join(p["purpose"] for p in decision.prohibited)) if prohibited
                  else "No prohibited purpose found in the purpose and question."})
    items.append({"id": "art53", "label": "Allowed purpose (Art. 53)",
                  "status": "no" if prohibited else _status(True if found else None),
                  "reason": ("Matches " + ", ".join(f"Art. {p['article']} {p['purpose']}" for p in found)) if found and not prohibited
                  else ("The stated purpose is prohibited." if prohibited else "No Art. 53 purpose recognised; staff must check.")})
    if decision.decision == APPROVE_STATISTICAL:
        items.append({"id": "art66", "label": "Data necessary and proportionate (Art. 66)", "status": "yes",
                      "reason": "Anonymised statistics are the least intrusive form of data."
                      if not asked_records else "Records were requested without explaining why statistics are not enough, "
                                                "so only statistics are released (data minimisation)."})
    elif records:
        items.append({"id": "art66", "label": "Data necessary and proportionate (Art. 66)", "status": "yes",
                      "reason": "The applicant explains why statistics are not enough: " + " ".join(decision.evidence[:2])})
    else:
        items.append({"id": "art66", "label": "Data necessary and proportionate (Art. 66)", "status": "no",
                      "reason": "Not assessed because the purpose is prohibited."})
    if asked_records:
        items.append({"id": "pseudo", "label": "Why anonymised data is not enough (records only)",
                      "status": _status(True if records else (False if not prohibited else None)),
                      "reason": "Justified in the application." if records else "Not justified in the application."})
    qualified = bool(re.search(QUALIFIED_ORG, org, re.I))
    items.append({"id": "qualified", "label": "Applicant qualified in the field", "status": "check",
                  "reason": (f"Organisation '{org}' looks like a research or public body; confirm credentials."
                             if qualified else f"Organisation '{org}': qualification must be shown by documents.")})
    items.append({"id": "safeguards", "label": "Technical and organisational safeguards", "status": "yes" if not records else "check",
                  "reason": "Only small-cell-protected statistics leave the HDAB." if not records
                  else "Processing only inside the SPE; staff must confirm the applicant's safeguards."})
    items.append({"id": "ethics", "label": "Ethics review if needed", "status": "check" if records else "yes",
                  "reason": "Record-level research: ethics approval must be attached." if records
                  else "Not needed for anonymised statistics."})
    items.append({"id": "legal_basis", "label": "Legal basis under GDPR", "status": "check" if records else "yes",
                  "reason": "Art. 9(2)(j) GDPR with EHDS permit; staff to confirm." if records
                  else "Anonymised data are outside the GDPR."})
    return items


def eligibility(answers: dict) -> dict:
    """Wizard for interested parties: what could they apply for?"""
    purpose = str(answers.get("purpose", ""))
    from .decision import find_prohibited
    bad = find_prohibited(purpose)
    if bad or answers.get("purpose_code") == "prohibited":
        return {"result": "not_eligible", "reason": "Prohibited purpose (Art. 54): " + (bad[0]["purpose"] if bad else "selected")}
    found = purposes(purpose) if purpose else []
    if not found and not answers.get("purpose_code"):
        return {"result": "not_eligible", "reason": "No allowed purpose from Art. 53 given."}
    need = answers.get("need", "statistics")
    if need == "records":
        why = str(answers.get("why_not_statistics", "")).strip()
        missing = [k for k in ("qualified", "safeguards", "ethics") if not answers.get(k)]
        if not why:
            return {"result": "statistics", "reason": "Without a reason why statistics are not enough you can apply for statistics (Art. 66, 69)."}
        if missing:
            return {"result": "not_eligible", "reason": "For records you need: " + ", ".join(missing) + " (Art. 68)."}
        return {"result": "spe", "reason": "You can apply for access in a secure processing environment (Art. 68, 73)."}
    return {"result": "statistics", "reason": "You can apply for anonymised statistics (Art. 69)."}
