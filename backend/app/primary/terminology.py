"""Code dictionary for the codes in the data: labels in English, German and Italian.

Translations come from the codes, never from free-text translation, so the
Patient Summary means the same in every language (MyHealth@EU principle).
"""
from __future__ import annotations

LABELS: dict[str, dict[str, str]] = {
    # ICD-10
    "C50.9": {"en": "Malignant neoplasm of breast", "de": "Bösartige Neubildung der Brustdrüse", "it": "Tumore maligno della mammella"},
    "E11.65": {"en": "Type 2 diabetes with hyperglycaemia", "de": "Diabetes mellitus Typ 2 mit Hyperglykämie", "it": "Diabete mellito di tipo 2 con iperglicemia"},
    "E11.9": {"en": "Type 2 diabetes without complications", "de": "Diabetes mellitus Typ 2 ohne Komplikationen", "it": "Diabete mellito di tipo 2 senza complicanze"},
    "E66.9": {"en": "Obesity", "de": "Adipositas", "it": "Obesità"},
    "F32.9": {"en": "Depressive episode", "de": "Depressive Episode", "it": "Episodio depressivo"},
    "I10": {"en": "Essential hypertension", "de": "Essentielle Hypertonie", "it": "Ipertensione essenziale"},
    "I48.0": {"en": "Paroxysmal atrial fibrillation", "de": "Paroxysmales Vorhofflimmern", "it": "Fibrillazione atriale parossistica"},
    "I48.2": {"en": "Chronic atrial fibrillation", "de": "Chronisches Vorhofflimmern", "it": "Fibrillazione atriale cronica"},
    "I50.9": {"en": "Heart failure", "de": "Herzinsuffizienz", "it": "Insufficienza cardiaca"},
    "I63.9": {"en": "Cerebral infarction (stroke)", "de": "Hirninfarkt (Schlaganfall)", "it": "Infarto cerebrale (ictus)"},
    "J18.9": {"en": "Pneumonia", "de": "Pneumonie", "it": "Polmonite"},
    "J44.9": {"en": "Chronic obstructive pulmonary disease", "de": "Chronisch obstruktive Lungenerkrankung (COPD)", "it": "Broncopneumopatia cronica ostruttiva (BPCO)"},
    "J45.9": {"en": "Asthma", "de": "Asthma bronchiale", "it": "Asma"},
    "K35.8": {"en": "Acute appendicitis", "de": "Akute Appendizitis", "it": "Appendicite acuta"},
    "N18.3": {"en": "Chronic kidney disease, stage 3", "de": "Chronische Nierenkrankheit, Stadium 3", "it": "Malattia renale cronica, stadio 3"},
    "N39.0": {"en": "Urinary tract infection", "de": "Harnwegsinfekt", "it": "Infezione delle vie urinarie"},
    "S72.0": {"en": "Fracture of neck of femur", "de": "Schenkelhalsfraktur", "it": "Frattura del collo del femore"},
    # ATC
    "A10AE04": {"en": "Insulin glargine", "de": "Insulin glargin", "it": "Insulina glargine"},
    "A10BA02": {"en": "Metformin", "de": "Metformin", "it": "Metformina"},
    "A10BJ06": {"en": "Semaglutide", "de": "Semaglutid", "it": "Semaglutide"},
    "A10BK03": {"en": "Empagliflozin", "de": "Empagliflozin", "it": "Empagliflozin"},
    "B01AA04": {"en": "Phenprocoumon", "de": "Phenprocoumon", "it": "Fenprocumone"},
    "B01AF01": {"en": "Rivaroxaban", "de": "Rivaroxaban", "it": "Rivaroxaban"},
    "B01AF02": {"en": "Apixaban", "de": "Apixaban", "it": "Apixaban"},
    "C03CA01": {"en": "Furosemide", "de": "Furosemid", "it": "Furosemide"},
    "C07AB07": {"en": "Bisoprolol", "de": "Bisoprolol", "it": "Bisoprololo"},
    "C08CA01": {"en": "Amlodipine", "de": "Amlodipin", "it": "Amlodipina"},
    "C09AA05": {"en": "Ramipril", "de": "Ramipril", "it": "Ramipril"},
    "C09CA06": {"en": "Candesartan", "de": "Candesartan", "it": "Candesartan"},
    "C10AA05": {"en": "Atorvastatin", "de": "Atorvastatin", "it": "Atorvastatina"},
    "N06AB06": {"en": "Sertraline", "de": "Sertralin", "it": "Sertralina"},
    "R03AK06": {"en": "Salmeterol/fluticasone", "de": "Salmeterol/Fluticason", "it": "Salmeterolo/fluticasone"},
    "R03BB04": {"en": "Tiotropium", "de": "Tiotropium", "it": "Tiotropio"},
    # LOINC
    "4548-4": {"en": "HbA1c", "de": "HbA1c", "it": "HbA1c (emoglobina glicata)"},
    "39156-5": {"en": "Body mass index", "de": "Body-Mass-Index", "it": "Indice di massa corporea"},
    "8480-6": {"en": "Systolic blood pressure", "de": "Systolischer Blutdruck", "it": "Pressione arteriosa sistolica"},
    "62238-1": {"en": "eGFR (kidney function)", "de": "eGFR (Nierenfunktion)", "it": "eGFR (funzione renale)"},
}

# drug classes that belong in the emergency strip
EMERGENCY_ATC = {
    "B01AC": {"en": "Antiplatelet medicine – bleeding risk", "de": "Thrombozytenaggregationshemmer – Blutungsrisiko", "it": "Antiaggregante piastrinico – rischio emorragico"},
    "B01A": {"en": "Anticoagulant – bleeding risk", "de": "Gerinnungshemmer – Blutungsrisiko", "it": "Anticoagulante – rischio emorragico"},
    "A10A": {"en": "Insulin – risk of hypoglycaemia", "de": "Insulin – Hypoglykämie-Risiko", "it": "Insulina – rischio di ipoglicemia"},
}
EMERGENCY_ICD = ("I48", "I50", "I63", "E11", "N18", "J44", "C50")

UI = {
    "problems": {"en": "Problems", "de": "Diagnosen", "it": "Problemi"},
    "medications": {"en": "Medications", "de": "Medikation", "it": "Farmaci"},
    "allergies": {"en": "Allergies", "de": "Allergien", "it": "Allergie"},
    "results": {"en": "Recent results", "de": "Aktuelle Befunde", "it": "Risultati recenti"},
    "no_allergy": {"en": "No allergy information in the source system", "de": "Keine Allergie-Information im Quellsystem",
                   "it": "Nessuna informazione sulle allergie nel sistema di origine"},
    "since": {"en": "since", "de": "seit", "it": "dal"},
    "emergency": {"en": "Emergency information", "de": "Notfall-Information", "it": "Informazioni di emergenza"},
}


def label(code: str | None, lang: str = "en", fallback: str | None = None) -> str:
    if not code:
        return fallback or ""
    entry = LABELS.get(code) or LABELS.get(code.split(".")[0])
    if entry:
        return entry.get(lang) or entry["en"]
    return fallback or code


def ui(key: str, lang: str) -> str:
    return UI[key].get(lang, UI[key]["en"])
