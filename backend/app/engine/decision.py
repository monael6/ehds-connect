"""Decision engine for HDAB requests (Regulation (EU) 2025/327, Chapter IV).

Order required by the task:
  1. prohibited purpose (Art. 54)                       -> REJECT                (54)
  2. "health data request"                              -> APPROVE_STATISTICAL   (53, 69)
  3. access application explaining why statistics
     are not enough                                     -> APPROVE_SPE           (53, 66, 68, 73)
  4. any other access application                       -> APPROVE_STATISTICAL   (53, 66, 69)

The decision is deterministic Python. An LLM may add a second opinion
(see engine/llm.py) but never overrides these rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

REJECT = "REJECT"
APPROVE_STATISTICAL = "APPROVE_STATISTICAL"
APPROVE_SPE = "APPROVE_SPE"

HEALTH_DATA_REQUEST = "health data request"
ACCESS_APPLICATION = "health data access application"

ARTICLES = {
    REJECT: [54],
    "step2": [53, 69],
    "step3": [53, 66, 68, 73],
    "step4": [53, 66, 69],
}

ARTICLE_TEXT = {
    53: "Purposes for which health data may be processed for secondary use",
    54: "Prohibited secondary use",
    66: "Data minimisation and purpose limitation",
    67: "Health data access applications",
    68: "Data permit",
    69: "Health data request (anonymised statistical data)",
    71: "Right to opt out of secondary use",
    73: "Secure processing environment",
}

# Art. 54(1) letters, each with patterns that signal the purpose.
PROHIBITED: list[tuple[str, str, list[str]]] = [
    ("54(1)(a)", "decisions detrimental to a person or group based on their health data", [
        r"\bdeny(ing)?\b.{0,40}\b(treatment|coverage|benefit|service)",
        r"\bdetrimental\b",
        r"\b(profil(e|ing))\b.{0,40}\b(individual|employee|applicant|customer)s?\b",
        r"\bidentify\b.{0,40}\b(individual|specific)\b.{0,20}\b(patient|person|people)s?\b.{0,40}\b(contact|target|exclude)",
        # re-identification: linking the data with the applicant's own list of people
        r"\bmatch\w*\b.{0,30}\b(records?|data)\b.{0,30}\b(with|against|to)\b.{0,30}\b(our|their|employee|customer|member|client|staff)\b",
        r"\bre-?identif",
    ]),
    ("54(1)(b)", "decisions on jobs, insurance, credit or worse terms for goods and services", [
        r"\b(insurance|insurer)\b.{0,60}\b(premium|pricing|price|tariff|underwrit|risk[- ]?scor|exclu|eligib)",
        r"\b(premium|premiums)\b.{0,60}\b(insur|policyholder|customer)",
        r"\bunderwrit(e|ing)\b",
        r"\b(credit|loan|mortgage)\b.{0,40}\b(scor|decision|eligib|approv|worthiness)",
        r"\b(hiring|recruit(ing|ment)?|job (applicant|offer)|employ(er|ment) decision|screen(ing)? (job )?applicants)\b",
        r"\bemployees?\b.{0,80}\b(list|match|contract|diagnos|sick|absen|renew|dismiss|hire|fire|promot)",
        r"\b(renew|terminat|extend|end)\w*\b.{0,20}\b(employment |work )?contracts?\b",
        r"\bbefore we (renew|hire|promote|extend|offer)",
    ]),
    ("54(1)(c)", "advertising or marketing", [
        r"\badverti[sz](e|ing|ement)s?\b",
        r"\bmarketing\b",
        r"\bsales (rep|representative|force|team|target)",
        r"\b(promot(e|ing|ion)|target(ed|ing)?)\b.{0,40}\b(product|drug|brand|campaign|prescrib)",
        r"\bcampaign\b.{0,40}\b(doctor|physician|prescriber|patient|customer)s?\b",
    ]),
    ("54(1)(d)", "giving the data to third parties not named in the permit", [
        r"\b(sell|resell|share|pass|transfer|licen[cs]e)\b.{0,40}\b(the )?data\b.{0,40}\b(to )?(third[- ]part|partner|client|broker|other compan)",
        r"\bdata broker",
    ]),
    ("54(1)(e)", "products or services that harm people or society (alcohol, tobacco, weapons, addictive products, misinformation)", [
        r"\b(alcohol|tobacco|cigarette|vape|vaping|nicotine)\b.{0,60}\b(product|sale|market|consum|brand|develop|flavou?r)",
        r"\b(develop|launch|market|sell|position|promot|design)\w*\b.{0,60}\b(nicotine|tobacco|alcohol|vape|e-cigarette|cigarette)",
        r"\bnicotine pouch",
        r"\b(weapon|weapons|explosive|bioweapon)\b",
        r"\b(gambling|betting)\b",
        r"\bmisinformation|disinformation\b",
    ]),
]

# Phrases showing the applicant explains why aggregated statistics are not enough.
STATS_NOT_ENOUGH = [
    r"statistic\w*.{0,60}\b(not|insufficient|cannot|can't|unable|inadequate|would not|wouldn't|do not|don't)\b",
    r"\b(not|cannot|can't|unable to)\b.{0,60}\b(statistic|aggregate|anonymi[sz]ed)\w*",
    r"\b(aggregate|anonymi[sz]ed)\w*\b.{0,40}\b(insufficient|not (be )?(enough|sufficient|adequate))",
    r"\b(record|patient|individual|row)[- ]level\b",
    r"\bpseudonymi[sz]ed (records|data)\b.{0,40}\b(needed|required|necessary)",
    r"\b(train|develop|validate)\w*\b.{0,40}\b(model|algorithm|classifier|machine learning|ai)\b",
    r"\blongitudinal\b.{0,40}\b(trajector|individual|per patient)",
    r"\bsurvival analysis|time[- ]to[- ]event|regression model",
]

# Text fields of a request that carry the applicant's own words.
TEXT_KEYS = ("purpose", "question", "description", "justification", "rationale", "why", "explanation",
             "reason", "aim", "aims", "objective", "objectives", "title", "summary",
             "intended_use", "use", "background", "necessity", "why_not_statistics")


@dataclass
class Decision:
    decision: str
    articles: list[int]
    step: int
    rule: str
    prohibited: list[dict] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    explanation: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "articles": self.articles,
            "matched_step": self.step,
            "rule": self.rule,
            "prohibited_purposes": self.prohibited,
            "evidence": self.evidence,
            "explanation": self.explanation,
            "article_titles": {str(a): ARTICLE_TEXT.get(a, "") for a in self.articles},
        }


def collect_text(obj, keys=TEXT_KEYS, _out=None) -> list[str]:
    """Free-text the applicant wrote (purpose, justification...), excluding definitions."""
    out = [] if _out is None else _out
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, str) and (kl in keys or any(t in kl for t in ("purpose", "justif", "reason", "why"))):
                out.append(v)
            elif isinstance(v, (dict, list)) and kl not in ("definitions", "metrics", "numbers", "statistics", "outputs"):
                collect_text(v, keys, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_text(v, keys, out)
    return out


def requested_as(request: dict) -> str:
    for k in ("requested_as", "request_type", "type"):
        v = request.get(k)
        if isinstance(v, str):
            return v.strip().lower()
    return ""


def _sentences_matching(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for sent in re.split(r"(?<=[.!?;])\s+|\n+", text):
        s = sent.strip()
        if s and any(re.search(p, s, re.I) for p in patterns):
            hits.append(s)
    return hits


def find_prohibited(text: str) -> list[dict]:
    found = []
    for letter, label, pats in PROHIBITED:
        ev = _sentences_matching(text, pats)
        if ev:
            found.append({"article": letter, "purpose": label, "evidence": ev[:3]})
    return found


def explains_stats_not_enough(text: str) -> list[str]:
    return _sentences_matching(text, STATS_NOT_ENOUGH)


def decide(request: dict) -> Decision:
    text = "\n".join(collect_text(request))
    kind = requested_as(request)

    prohibited = find_prohibited(text)
    if prohibited:
        p = prohibited[0]
        return Decision(REJECT, ARTICLES[REJECT], 1, "Prohibited purpose (Art. 54)", prohibited,
                        [e for x in prohibited for e in x["evidence"]],
                        _explain(REJECT, purpose=p["purpose"]))

    if kind == HEALTH_DATA_REQUEST or (kind and "request" in kind and "application" not in kind):
        return Decision(APPROVE_STATISTICAL, ARTICLES["step2"], 2,
                        "Health data request -> anonymised statistics (Art. 53, 69)",
                        explanation=_explain(APPROVE_STATISTICAL, step=2))

    reasons = explains_stats_not_enough(text)
    if reasons:
        return Decision(APPROVE_SPE, ARTICLES["step3"], 3,
                        "Access application that explains why statistics are not enough -> SPE (Art. 53, 66, 68, 73)",
                        evidence=reasons[:3], explanation=_explain(APPROVE_SPE))

    return Decision(APPROVE_STATISTICAL, ARTICLES["step4"], 4,
                    "Access application without a reason why statistics are not enough -> statistics (Art. 53, 66, 69)",
                    explanation=_explain(APPROVE_STATISTICAL, step=4))


def _explain(decision: str, purpose: str = "", step: int = 0) -> dict[str, str]:
    if decision == REJECT:
        return {
            "en": f"Your request is rejected. Its purpose ({purpose}) is prohibited for secondary use of health data "
                  f"under Art. 54 of the EHDS Regulation. No data or statistics are provided.",
            "de": f"Ihr Antrag wird abgelehnt. Der Zweck ({purpose}) ist für die Sekundärnutzung von Gesundheitsdaten "
                  f"nach Art. 54 EHDS-Verordnung verboten. Es werden keine Daten oder Statistiken bereitgestellt.",
            "it": f"La richiesta è respinta. La finalità ({purpose}) è vietata per l'uso secondario dei dati sanitari "
                  f"ai sensi dell'art. 54 del regolamento EHDS. Non vengono forniti dati né statistiche.",
        }
    if decision == APPROVE_SPE:
        return {
            "en": "Your access application is approved for a secure processing environment (Art. 53, 66, 68, 73). "
                  "You explained why anonymised statistics are not enough. Only the patients and record types you "
                  "need are copied into the environment, pseudonymised, without patients who opted out. You can "
                  "analyse them there, but you cannot download them.",
            "de": "Ihr Zugangsantrag wird für eine sichere Verarbeitungsumgebung genehmigt (Art. 53, 66, 68, 73). "
                  "Sie haben begründet, warum anonyme Statistiken nicht reichen. Nur die benötigten Personen und "
                  "Datensatztypen werden pseudonymisiert und ohne Personen mit Widerspruch bereitgestellt. Sie können "
                  "dort rechnen, aber nichts herunterladen.",
            "it": "La domanda di accesso è approvata in un ambiente di trattamento sicuro (art. 53, 66, 68, 73). "
                  "Ha spiegato perché le statistiche anonime non bastano. Solo i pazienti e i tipi di dati necessari "
                  "vengono copiati, pseudonimizzati e senza chi ha esercitato l'opt-out. Può analizzarli ma non scaricarli.",
        }
    if step == 4:
        return {
            "en": "Your access application is answered with anonymised statistics (Art. 53, 66, 69). You did not "
                  "explain why statistics are not enough, so under data minimisation (Art. 66) no records are released.",
            "de": "Ihr Zugangsantrag wird mit anonymen Statistiken beantwortet (Art. 53, 66, 69). Sie haben nicht "
                  "begründet, warum Statistiken nicht reichen. Wegen Datenminimierung (Art. 66) gibt es keine Einzeldaten.",
            "it": "La domanda di accesso riceve statistiche anonime (art. 53, 66, 69). Non ha spiegato perché le "
                  "statistiche non bastano, quindi per la minimizzazione dei dati (art. 66) non vengono rilasciati record.",
        }
    return {
        "en": "Your health data request is approved. You receive anonymised statistics (Art. 53, 69). "
              "Groups with fewer than 10 patients are shown as <10 or suppressed, and patients who opted out are never counted.",
        "de": "Ihre Datenanfrage wird genehmigt. Sie erhalten anonyme Statistiken (Art. 53, 69). "
              "Gruppen mit weniger als 10 Personen erscheinen als <10 oder unterdrückt, Personen mit Widerspruch werden nie mitgezählt.",
        "it": "La richiesta di dati sanitari è approvata. Riceve statistiche anonime (art. 53, 69). "
              "I gruppi con meno di 10 pazienti sono mostrati come <10 o soppressi; chi ha esercitato l'opt-out non viene mai contato.",
    }
