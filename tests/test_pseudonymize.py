"""Tests for pseudonymization."""

from pipeline.pseudonymize import pseudonymize_documents, PseudoMapping, redact_for_log


PATIENT = {
    "patient_id": "P001",
    "vorname": "Hermine",
    "nachname": "Bruckner",
    "geburtsdatum": "1952-04-17",
    "geschlecht": "weiblich",
    "fiktive_versicherungsnummer": "FAKE-7241-170452",
    "wohnort_bundesland": "Niederösterreich",
}

DOCS = [
    {
        "id": "P001-D004",
        "typ": "Aufnahmebefund",
        "datum": "2024-09-02T16:05",
        "titel": "Aufnahme",
        "text": (
            "Pat. Hermine Bruckner, *17.04.1952, w.\n"
            "Versicherungsnummer: FAKE-7241-170452\n"
            "Behandelt in Landesklinikum Musterstadt, Station UC-2.\n"
            "Dr. Stefan Kralik untersucht die Patientin.\n"
            "Diagnose: Schenkelhalsfraktur."
        ),
        "autor_rolle": "Assistenzarzt",
        "einrichtung": "Landesklinikum Musterstadt",
        "fachrichtung": "Unfallchirurgie",
    }
]


def test_patient_name_replaced():
    pseudo_docs, mapping = pseudonymize_documents(PATIENT, DOCS)
    assert "Hermine" not in pseudo_docs[0]["text"]
    assert "Bruckner" not in pseudo_docs[0]["text"]
    assert "[PAT-NAME]" in pseudo_docs[0]["text"]


def test_insurance_number_replaced():
    pseudo_docs, mapping = pseudonymize_documents(PATIENT, DOCS)
    assert "FAKE-7241-170452" not in pseudo_docs[0]["text"]
    assert "[PAT-INSID]" in pseudo_docs[0]["text"]


def test_dob_replaced():
    pseudo_docs, mapping = pseudonymize_documents(PATIENT, DOCS)
    assert "17.04.1952" not in pseudo_docs[0]["text"]
    assert "[PAT-DOB]" in pseudo_docs[0]["text"]


def test_facility_replaced():
    pseudo_docs, mapping = pseudonymize_documents(PATIENT, DOCS)
    assert "Landesklinikum Musterstadt" not in pseudo_docs[0]["text"]
    assert "[FAC-" in pseudo_docs[0]["text"]


def test_original_docs_unchanged():
    """Original documents must not be mutated."""
    original_text = DOCS[0]["text"]
    pseudonymize_documents(PATIENT, DOCS)
    assert DOCS[0]["text"] == original_text


def test_mapping_is_stable():
    """Same facility always gets the same token within one call."""
    docs = [
        {**DOCS[0], "id": "D1", "text": "Landesklinikum Musterstadt"},
        {**DOCS[0], "id": "D2", "text": "Landesklinikum Musterstadt"},
    ]
    pseudo_docs, mapping = pseudonymize_documents(PATIENT, docs)
    token1 = pseudo_docs[0]["text"]
    token2 = pseudo_docs[1]["text"]
    assert token1 == token2
    assert len(mapping.facility_map) == 1


def test_date_shift():
    docs = [{**DOCS[0], "text": "Datum: 2024-09-02, alt: 01.09.2024"}]
    pseudo_docs, _ = pseudonymize_documents(PATIENT, docs, shift_days=7)
    assert "2024-09-09" in pseudo_docs[0]["text"]
    assert "08.09.2024" in pseudo_docs[0]["text"]


def test_patient_token_has_correct_format():
    _, mapping = pseudonymize_documents(PATIENT, DOCS)
    assert mapping.patient_token.startswith("PT-")
    assert len(mapping.patient_token) == 9  # "PT-" + 6 hex chars


def test_redact_for_log_removes_real_name():
    _, mapping = pseudonymize_documents(PATIENT, DOCS)
    log_text = f"Processing patient Hermine Bruckner"
    redacted = redact_for_log(log_text, mapping)
    assert "Hermine" not in redacted
    assert "Bruckner" not in redacted
