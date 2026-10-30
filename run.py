"""
run.py – CLI entry point for the IPS pipeline.

Usage:
    python run.py --patient P001 --mode synthetic
    python run.py --patient P001 --mode pseudonymized --deployment deployment.yaml
    python run.py --patient P001 --mode synthetic --shift-days 30

Steps:
    1. Data protection gate
    2. Pseudonymization
    3. LLM extraction
    4. Quote verification
    5. Terminology validation
    6. FHIR mapping
    7. Validation
    8. Evaluation (synthetic mode)
    9. Discharge summary
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Load .env before any os.environ reads (no-op if python-dotenv not installed
# or .env doesn't exist — Docker Compose injects variables directly).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pipeline.crypto import write_output
from pipeline.evaluate import evaluate
from pipeline.extract import extract
from pipeline.fhir_mapping import map_to_fhir
from pipeline.gate import Mode, run_gate
from pipeline.llm_client import LLMClient
from pipeline.models import ExtractionIntermediate
from pipeline.pseudonymize import pseudonymize_documents
from pipeline.summary import generate_summary
from pipeline.terminology import validate_terminology
from pipeline.validate import validate_bundle
from pipeline.verify_quotes import verify_quotes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run")

PATIENTS_DIR = Path("patients")
OUTPUT_DIR = Path("output")


def load_patient_data(patient_id: str) -> tuple[dict, list[dict]]:
    base = PATIENTS_DIR / patient_id
    patient_file = base / "patient.json"
    docs_file = base / "documents.json"

    if not patient_file.exists():
        logger.error("patient.json not found: %s", patient_file)
        sys.exit(1)
    if not docs_file.exists():
        logger.error("documents.json not found: %s", docs_file)
        sys.exit(1)

    patient = json.loads(patient_file.read_text(encoding="utf-8"))
    documents = json.loads(docs_file.read_text(encoding="utf-8"))
    return patient, documents


def write_audit_entry(
    audit_path: Path,
    event: str,
    patient_token: str,
    mode: str,
    model: str,
    success: bool,
    detail: str = "",
) -> None:
    """Append one JSON-lines entry to the audit log. NO clinical content in logs."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "patient_token": patient_token,   # pseudonymized — never real name
        "mode": mode,
        "model": model,
        "success": success,
        "detail": detail,
        "runner": "run.py",
    }
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="IPS pipeline")
    parser.add_argument("--patient", required=True, help="Patient ID, e.g. P001")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "pseudonymized", "real"],
        default="synthetic",
        help="Data protection mode",
    )
    parser.add_argument(
        "--deployment",
        default="deployment.yaml",
        help="Path to deployment.yaml (required for pseudonymized/real)",
    )
    parser.add_argument(
        "--shift-days",
        type=int,
        default=0,
        help="Date shift in days for pseudonymization (0 = no shift)",
    )
    parser.add_argument(
        "--at-aps",
        action="store_true",
        help="Also validate against Austrian Patient Summary IG (stretch goal)",
    )
    args = parser.parse_args()

    patient_id: str = args.patient
    mode: Mode = args.mode
    t_start = time.perf_counter()

    # ── Output directory ───────────────────────────────────────────────────────
    output_dir = OUTPUT_DIR / patient_id
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit_log.jsonl"

    # ── Load data ──────────────────────────────────────────────────────────────
    logger.info("Loading patient data for %s …", patient_id)
    patient_json, documents = load_patient_data(patient_id)
    document_texts = [d.get("text", "") for d in documents]

    # ── Step 1: Data protection gate ──────────────────────────────────────────
    logger.info("Step 1: Data protection gate (mode=%s) …", mode)
    gate_result = run_gate(
        mode=mode,
        patient_id=patient_id,
        document_texts=document_texts,
        deployment_yaml_path=Path(args.deployment) if mode != "synthetic" else None,
    )
    for w in gate_result.warnings:
        logger.warning("%s", w)

    # ── Step 2: Pseudonymization ──────────────────────────────────────────────
    logger.info("Step 2: Pseudonymization …")
    pseudo_docs, pseudo_mapping = pseudonymize_documents(
        patient_json=patient_json,
        documents=documents,
        shift_days=args.shift_days,
    )
    patient_token = pseudo_mapping.patient_token
    logger.info("Patient token: %s", patient_token)
    write_audit_entry(audit_path, "pipeline_start", patient_token, mode, "", True)

    # ── Step 3: LLM extraction ────────────────────────────────────────────────
    logger.info("Step 3: LLM extraction …")
    llm = LLMClient()
    try:
        intermediate: ExtractionIntermediate = extract(patient_token, pseudo_docs, llm)
        write_audit_entry(audit_path, "extraction_complete", patient_token, mode, llm._model, True,
                          f"items={len(intermediate.all_included_items())}")
    except Exception as exc:
        write_audit_entry(audit_path, "extraction_failed", patient_token, mode, "", False, str(exc)[:200])
        logger.error("Extraction failed: %s", exc)
        sys.exit(1)

    # ── Step 4: Quote verification ────────────────────────────────────────────
    logger.info("Step 4: Quote verification …")
    intermediate, failed_quotes = verify_quotes(intermediate, pseudo_docs)
    write_audit_entry(
        audit_path, "quote_verification", patient_token, mode, llm._model, True,
        f"failed={len(failed_quotes)}"
    )

    # ── Step 5: Terminology validation ───────────────────────────────────────
    logger.info("Step 5: Terminology validation …")
    intermediate = validate_terminology(intermediate)

    # Save intermediate JSON
    inter_path = output_dir / "extraction_intermediate.json"
    write_output(
        inter_path,
        intermediate.model_dump_json(indent=2),
        mode,
    )
    logger.info("Intermediate JSON saved to %s", inter_path)

    # ── Step 6: FHIR mapping ──────────────────────────────────────────────────
    logger.info("Step 6: FHIR mapping …")
    fhir_bundle = map_to_fhir(intermediate, patient_json, pseudo_mapping, documents)

    bundle_path = output_dir / "ips_bundle.json"
    write_output(
        bundle_path,
        json.dumps(fhir_bundle, ensure_ascii=False, indent=2),
        mode,
    )
    logger.info("FHIR Bundle saved to %s", bundle_path)
    write_audit_entry(audit_path, "fhir_mapping_complete", patient_token, mode, llm._model, True)

    # ── Step 7: Validation ────────────────────────────────────────────────────
    logger.info("Step 7: FHIR validation …")
    val_report = validate_bundle(fhir_bundle, include_at_aps=args.at_aps)
    val_path = output_dir / "validation_report.json"
    write_output(
        val_path,
        json.dumps(val_report.to_dict(), ensure_ascii=False, indent=2),
        mode,
    )
    logger.info("Validation status: %s (%d errors, %d warnings)",
                val_report.status, len(val_report.errors), len(val_report.warnings))
    write_audit_entry(
        audit_path, "validation_complete", patient_token, mode, "", val_report.status != "failed",
        f"status={val_report.status}"
    )

    # ── Step 8: Evaluation (synthetic only) ──────────────────────────────────
    if mode == "synthetic":
        gt_path = PATIENTS_DIR / patient_id / "ground_truth_ips.json"
        if gt_path.exists():
            logger.info("Step 8: Evaluating against ground truth …")
            eval_report = evaluate(intermediate, gt_path)
            eval_path = output_dir / "evaluation_report.json"
            write_output(
                eval_path,
                json.dumps(eval_report.to_dict(), ensure_ascii=False, indent=2),
                mode,
            )
            logger.info(
                "Evaluation: precision=%.3f recall=%.3f f1=%.3f leaks=%d",
                eval_report.overall_precision,
                eval_report.overall_recall,
                eval_report.overall_f1,
                len(eval_report.must_not_include_leaks),
            )
        else:
            logger.info("Step 8: No ground truth file found, skipping evaluation.")

    # ── Step 9: Discharge summary ─────────────────────────────────────────────
    logger.info("Step 9: Generating discharge summary …")
    summary_md = generate_summary(intermediate, patient_json, llm)
    summary_path = output_dir / "discharge_summary_draft.md"
    write_output(summary_path, summary_md, mode)
    logger.info("Discharge summary saved to %s", summary_path)

    elapsed = time.perf_counter() - t_start
    write_audit_entry(
        audit_path, "pipeline_complete", patient_token, mode, llm._model, True,
        f"elapsed_s={elapsed:.1f}"
    )
    logger.info("Pipeline complete in %.1fs. Outputs in %s/", elapsed, output_dir)


if __name__ == "__main__":
    main()
