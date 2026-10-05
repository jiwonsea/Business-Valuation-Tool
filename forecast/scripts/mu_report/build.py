"""Phase-restricted entry point for the MU report pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import yaml

if __package__ in {None, ""}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from forecast.scripts.mu_report.extract import build_sources
    from forecast.scripts.mu_report.facts import dryrun_manifest_from_extracts, fixture_manifest
    from forecast.scripts.mu_report.narrative import e2b_manifest_from_inputs
    from forecast.scripts.mu_report.render import render_dryrun_bundle, render_e2b_bundle, render_fixture_bundle
else:
    from .extract import build_sources
    from .facts import dryrun_manifest_from_extracts, fixture_manifest
    from .narrative import e2b_manifest_from_inputs
    from .render import render_dryrun_bundle, render_e2b_bundle, render_fixture_bundle


REPO_ROOT = Path(__file__).resolve().parents[3]
E2B_BASELINES = {
    "forecast/inputs/mu_fy2026q4_report_assumptions.yaml": "292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539",
    "forecast/REVIEW_CODEX_mu_report_rle_values_r2.md": "8012d34a8881567568b20fc440771156390f2426b942c36c8b9f33f0847fa74a",
    "forecast/inputs/mu_fy2026q4_narrative_ed1.yaml": "85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d",
}


def _run_e2b_preflight() -> dict[str, object]:
    from pypdf import PdfReader

    from forecast.scripts.mu_report.extract import normalize_pdf_text
    from forecast.scripts.mu_report.gates import (
        gate_g1_inputs,
        gate_g2_freeze_display,
        gate_g3_financial_identities,
        gate_g3b_balance_sheet,
        gate_g3c_cash_flow,
        gate_g3f_scored_source,
        gate_g7_templates_and_io,
        gate_g9_cutoff,
        gate_g12_manifest,
        gate_g14_provenance,
        gate_g15_toc,
        gate_g17_net_cash_label,
        gate_g18_hygiene,
        gate_g19_bridge,
        gate_g20_phase_audit,
        gate_narrative_contract,
    )
    from forecast.scripts.mu_report.inputs import EvidenceReader, PACKAGE_DIR, load_pins

    for relative, expected in E2B_BASELINES.items():
        actual = hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"E2-B baseline SHA mismatch: {relative}: {actual}")

    reader = EvidenceReader("E2-B")
    for phase in ("E2-A", "E2-B"):
        for item in load_pins()[phase]:
            if item["sha256"] is not None:
                reader.read_bytes(item["path"])
    gate_g1_inputs(EvidenceReader("E2-B"))
    ex991_path = "logs/mu/fy2026q4/postprint/ex991.htm"
    scored_path = "forecast/reports/mu_fy2026q4_SCORED.md"
    remarks_path = "logs/mu/fy2026q4/postprint/remarks.pdf"
    ex991_text = reader.read_text(ex991_path)
    scored_text = reader.read_text(scored_path)
    remarks_pdf = PdfReader(BytesIO(reader.read_bytes(remarks_path)))
    remarks_text = normalize_pdf_text(" ".join(page.extract_text() or "" for page in remarks_pdf.pages))
    assumptions_path = REPO_ROOT / "forecast/inputs/mu_fy2026q4_report_assumptions.yaml"
    narrative_path = REPO_ROOT / "forecast/inputs/mu_fy2026q4_narrative_ed1.yaml"
    manifest, narrative, assumptions, values = e2b_manifest_from_inputs(
        PACKAGE_DIR / "sources",
        narrative_path.read_text(encoding="utf-8"),
        assumptions_path.read_text(encoding="utf-8"),
        ex991_text,
        remarks_text,
        scored_text,
        {
            "SRC-EX991-FQ4FY26": ex991_path,
            "SRC-REMARKS-FQ4FY26": remarks_path,
            "SRC-SCORED-FQ4FY26": scored_path,
            "SRC-RLE-FY27": "forecast/inputs/mu_fy2026q4_report_assumptions.yaml",
            "SRC-PRICE-1": "logs/mu/fy2026q4/postprint/price_2026-10-01_src1.png",
            "SRC-PRICE-2": "logs/mu/fy2026q4/postprint/price_2026-10-01_src2.png",
        },
    )
    gate_narrative_contract(narrative, manifest)
    gate_g3f_scored_source(manifest, scored_text)
    gate_g12_manifest(manifest)
    gate_g14_provenance(manifest)
    gate_g19_bridge(manifest)
    gate_g9_cutoff([
        {"section": "PREREG_A", "information_class": "PRE_PRINT"},
        {"section": "RLE", "basis": "RLE"},
    ])
    gate_g7_templates_and_io([
        *PACKAGE_DIR.glob("*.py"),
        PACKAGE_DIR / "i18n" / "ko.yaml",
        PACKAGE_DIR / "i18n" / "en.yaml",
    ])
    locale_configs = {
        locale: yaml.safe_load((PACKAGE_DIR / "i18n" / f"{locale}.yaml").read_text(encoding="utf-8"))
        for locale in ("ko", "en")
    }
    gate_g15_toc({locale: config["sections"] for locale, config in locale_configs.items()})
    gate_g17_net_cash_label(locale_configs)
    for year in (2023, 2024, 2025):
        suffix = f"FY{year}A"
        gate_g3_financial_identities({
            key: float(manifest.fact(f"is.{key}.{suffix}").raw_value)
            for key in (
                "revenue", "cogs", "gross_profit", "r_and_d", "sg_and_a", "restructuring", "other_operating",
                "operating_income", "interest_income", "interest_expense", "other_nonoperating", "pretax_income",
                "tax", "equity_method", "net_income", "diluted_eps", "diluted_shares",
            )
        })
        gate_g3b_balance_sheet({
            key: float(manifest.fact(f"bs.{key}.{suffix}").raw_value)
            for key in ("total_assets", "total_liabilities", "total_equity")
        })
        gate_g3c_cash_flow({
            "operating": float(manifest.fact(f"cf.operating_cash_flow.{suffix}").raw_value),
            "investing": float(manifest.fact(f"cf.investing_cash_flow.{suffix}").raw_value),
            "financing": float(manifest.fact(f"cf.financing_cash_flow.{suffix}").raw_value),
            "fx": float(manifest.fact(f"cf.fx_effect.{suffix}").raw_value),
            "cash_change": float(manifest.fact(f"cf.cash_change.{suffix}").raw_value),
        })
    freeze = json.loads((PACKAGE_DIR / "sources" / "freeze_prereg.json").read_text(encoding="utf-8"))
    expected = {
        "revenue": next(row for row in freeze["prereg_a_display_rows"] if row["label_markdown"] == "매출")["display_text"]["base"],
        "eps": next(row for row in freeze["prereg_a_display_rows"] if row["label_markdown"] == "**GAAP 희석 EPS**")["display_text"]["base"],
    }
    gate_g2_freeze_display(expected, {
        "revenue": manifest.fact("prereg.revenue.base.FY2026Q4.PREREG_A").display["ko"],
        "eps": manifest.fact("is.eps_gaap.FY2026Q4.PREREG_A").display["ko"],
    })
    gate_g20_phase_audit(reader, ("E2-A", "E2-B"))
    hygiene_paths = [
        *PACKAGE_DIR.glob("*.py"),
        PACKAGE_DIR / "i18n" / "ko.yaml",
        PACKAGE_DIR / "i18n" / "en.yaml",
        narrative_path,
        assumptions_path,
    ]
    gate_g18_hygiene(hygiene_paths)
    return {
        "phase": "E2B",
        "fact_bindings": values,
        "manifest": manifest,
        "narrative": narrative,
        "assumptions": assumptions,
        "reader": reader,
        "gates": {
            "G-1": "PASS", "G-2": "PASS", "G-3": "PASS", "G-3f": "PASS", "G-4": "NOT_APPLICABLE_PRE_RENDER",
            "G-5": "NOT_APPLICABLE_PRE_RENDER", "G-6": "NOT_APPLICABLE_PRE_RENDER", "G-7": "PASS",
            "G-8": "NOT_APPLICABLE_PRE_RENDER", "G-9": "PASS", "G-10": "NOT_APPLICABLE_PRE_RENDER",
            "G-11": "NOT_APPLICABLE_PRE_RENDER", "G-12": "PASS", "G-12b": "DEFERRED_RENDER",
            "G-12c": "PENDING_CONFLICT_CONFIRMATION", "G-13": "DEFERRED_RENDER", "G-14": "PASS",
            "G-15": "PASS_STRUCTURE", "G-16": "DEFERRED_RENDER", "G-17": "PASS_CONFIG",
            "G-18": "PASS", "G-19": "PASS", "G-20": "PASS", "G-21": "DEFERRED_RENDER",
        },
    }


def _run_dryrun(output: Path) -> None:
    from pypdf import PdfReader

    from forecast.scripts.mu_report.extract import normalize_pdf_text
    from forecast.scripts.mu_report.gates import (
        DRYRUN_CONFLICT,
        gate_categorical_verbatim,
        gate_dryrun_boundary,
        gate_dryrun_placeholders,
        gate_dryrun_watermark,
        gate_g1_inputs,
        gate_g2_freeze_display,
        gate_g3_financial_identities,
        gate_g3b_balance_sheet,
        gate_g3c_cash_flow,
        gate_g3d_company_fcf,
        gate_g7_templates_and_io,
        gate_g9_cutoff,
        gate_g12_manifest,
        gate_g12b_disclaimers,
        gate_g13_charts,
        gate_g13b_chart_identity,
        gate_g13c_chart_semantics,
        gate_g14_provenance,
        gate_g15b_localized_ui,
        gate_g16_caption,
        gate_g18_hygiene,
        gate_g19_bridge,
        gate_g20_audit,
        gate_g21_formats,
    )
    from forecast.scripts.mu_report.inputs import EvidenceReader, PACKAGE_DIR

    source_dir = output / "sources"
    build_sources(source_dir, write_runtime_log=False)
    audit_payload = (source_dir / "input_audit.json").read_bytes()
    manifest = dryrun_manifest_from_extracts(source_dir)
    gate_dryrun_boundary(output, manifest, audit_payload)

    reader = EvidenceReader("E2-A")
    gate_g1_inputs(reader)
    gate_g20_audit(reader)
    remarks = json.loads((source_dir / "prepared_remarks.json").read_text(encoding="utf-8"))
    remarks_pdf = PdfReader(BytesIO(reader.read_bytes(remarks["source"]["path"])))
    remarks_text = normalize_pdf_text(" ".join(page.extract_text() or "" for page in remarks_pdf.pages))
    gate_categorical_verbatim(
        [value for metrics in remarks["product_metrics"].values() for value in metrics.values()],
        remarks_text,
    )
    freeze = json.loads((source_dir / "freeze_prereg.json").read_text(encoding="utf-8"))
    expected = {
        "revenue": next(row for row in freeze["prereg_a_display_rows"] if row["label_markdown"] == "매출")["display_text"]["base"],
        "eps": next(row for row in freeze["prereg_a_display_rows"] if row["label_markdown"] == "**GAAP 희석 EPS**")["display_text"]["base"],
    }
    actual = {
        "revenue": manifest.fact("prereg.revenue.base.FY2026Q4.PREREG_A").display["ko"],
        "eps": manifest.fact("is.eps_gaap.FY2026Q4.PREREG_A").display["ko"],
    }
    gate_g2_freeze_display(expected, actual)
    for year in (2023, 2024, 2025):
        suffix = f"FY{year}A"
        gate_g3_financial_identities({key: float(manifest.fact(f"is.{key}.{suffix}").raw_value) for key in (
            "revenue", "cogs", "gross_profit", "r_and_d", "sg_and_a", "restructuring", "other_operating",
            "operating_income", "interest_income", "interest_expense", "other_nonoperating", "pretax_income",
            "tax", "equity_method", "net_income", "diluted_eps", "diluted_shares",
        )})
        gate_g3b_balance_sheet({
            "total_assets": float(manifest.fact(f"bs.total_assets.{suffix}").raw_value),
            "total_liabilities": float(manifest.fact(f"bs.total_liabilities.{suffix}").raw_value),
            "total_equity": float(manifest.fact(f"bs.total_equity.{suffix}").raw_value),
        })
        gate_g3c_cash_flow({
            "operating": float(manifest.fact(f"cf.operating_cash_flow.{suffix}").raw_value),
            "investing": float(manifest.fact(f"cf.investing_cash_flow.{suffix}").raw_value),
            "financing": float(manifest.fact(f"cf.financing_cash_flow.{suffix}").raw_value),
            "fx": float(manifest.fact(f"cf.fx_effect.{suffix}").raw_value),
            "cash_change": float(manifest.fact(f"cf.cash_change.{suffix}").raw_value),
        })
    debt = json.loads((source_dir / "debt_fcf.json").read_text(encoding="utf-8"))["company_defined_fq3_fy26"]
    gate_g3d_company_fcf(debt)
    gate_g7_templates_and_io([
        *PACKAGE_DIR.glob("*.py"),
        PACKAGE_DIR / "i18n" / "ko.yaml",
        PACKAGE_DIR / "i18n" / "en.yaml",
    ])
    gate_g9_cutoff([{"section": "PREREG_A", "information_class": "PRE_PRINT"}])
    gate_g12_manifest(manifest)
    gate_g14_provenance(manifest)
    gate_g19_bridge(manifest)
    outputs = render_dryrun_bundle(manifest, output, audit_payload)
    markdown = {locale: outputs[f"md_{locale}"].read_text(encoding="utf-8") for locale in ("ko", "en")}
    gate_g12b_disclaimers(markdown)
    chart_manifests = {
        locale: json.loads(outputs[f"chart_manifest_{locale}"].read_text(encoding="utf-8"))
        for locale in ("ko", "en")
    }
    gate_g15b_localized_ui(chart_manifests, markdown)
    for chart_manifest in chart_manifests.values():
        gate_g13_charts(chart_manifest)
        gate_g13b_chart_identity(manifest, chart_manifest)
        gate_g13c_chart_semantics(manifest, chart_manifest)
        gate_dryrun_placeholders(manifest, chart_manifest)
        for chart in chart_manifest.values():
            gate_g16_caption(chart["caption"])
    for locale in ("ko", "en"):
        texts = [page.extract_text() or "" for page in PdfReader(outputs[f"pdf_{locale}"]).pages]
        gate_dryrun_watermark(texts, "PRE-PRINT DRY RUN · 배포 금지" if locale == "ko" else "PRE-PRINT DRY RUN · NOT FOR DISTRIBUTION")
        gate_dryrun_watermark(texts, DRYRUN_CONFLICT[locale])
    gate_g21_formats(outputs, dryrun=True)
    text_suffixes = {".py", ".yaml", ".yml", ".json", ".md", ".html", ".mjs"}
    gate_g18_hygiene(path for path in output.rglob("*") if path.is_file() and path.suffix.lower() in text_suffixes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=["E2-A", "E2-B", "E2B", "E2-C", "DRYRUN"])
    parser.add_argument("--edition", default="1", choices=["1", "2", "dryrun"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.phase == "DRYRUN":
        if args.edition != "dryrun" or args.output_dir is not None:
            parser.error("DRYRUN requires --edition dryrun and manages its own output directory")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = REPO_ROOT / "logs" / "_mu_report_runs" / f"dryrun_{stamp}"
        _run_dryrun(output)
        print(output.relative_to(REPO_ROOT).as_posix())
        return 0
    if args.phase in {"E2-B", "E2B"}:
        if args.edition != "1" or args.output_dir is not None:
            parser.error("E2B preflight requires --edition 1 and does not accept --output-dir")
        result = _run_e2b_preflight()
        conflict_path = REPO_ROOT / "forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml"
        if not conflict_path.exists():
            printable = {
                key: value
                for key, value in result.items()
                if key not in {"manifest", "narrative", "assumptions", "reader"}
            }
            printable["status"] = "BLOCKED_CONFLICT_CONFIRMATION_MISSING_NO_RENDER"
            print(json.dumps(printable, ensure_ascii=False, indent=2, sort_keys=True))
            return 2
        kst = timezone(timedelta(hours=9))
        render_started = datetime.now(kst)
        from forecast.scripts.mu_report.inputs import load_conflict_confirmation

        conflict = load_conflict_confirmation(conflict_path, "ed1", render_started)
        age = render_started - conflict.confirmed_at_kst
        if conflict.status != "not_held" or conflict.edition != "ed1" or not timedelta(0) <= age < timedelta(hours=24):
            parser.error("E2B conflict confirmation is invalid, future-dated, expired, or for another edition")
        reader = result["reader"]
        outputs, state = render_e2b_bundle(
            result["manifest"],
            result["narrative"],
            result["assumptions"],
            conflict,
            REPO_ROOT / "forecast" / "reports",
            reader.audit_payload(),
            render_started,
        )
        failures: dict[str, str] = {}
        passes: list[str] = []

        def run_gate(name: str, function, *gate_args):
            try:
                value = function(*gate_args)
                passes.append(name)
                return value
            except Exception as exc:
                failures[name] = f"{type(exc).__name__}: {exc}"
                return None

        from forecast.scripts.mu_report.gates import (
            gate_ed1_rendered,
            gate_g12b_disclaimers,
            gate_g12c_conflict,
            gate_g13_charts,
            gate_g13b_chart_identity,
            gate_g13c_chart_semantics,
            gate_g15_parity,
            gate_g15b_localized_ui,
            gate_g16_caption,
            gate_g17_labels,
            gate_g17_net_cash_label,
            gate_g17b_consensus,
            gate_g18_hygiene,
            gate_g21_formats,
            gate_g23_availability,
            gate_g24_raw_markup,
            gate_g25_cover_dates,
            gate_inventory_days,
            gate_market_data_box,
            gate_narrative_contract,
            gate_theme,
            gate_trailing_pb,
        )
        from forecast.scripts.mu_report.inputs import PACKAGE_DIR, atomic_write

        manifest = result["manifest"]
        rendered_texts = state["rendered_texts"]
        references = state["references"]
        chart_manifests = state["chart_manifests"]
        locale_configs = {
            locale: yaml.safe_load((PACKAGE_DIR / "i18n" / f"{locale}.yaml").read_text(encoding="utf-8"))
            for locale in ("ko", "en")
        }
        run_gate("G-4 inventory days", gate_inventory_days, manifest)
        run_gate(
            "G-5 trailing P/B",
            gate_trailing_pb,
            manifest,
            {
                "price_date": str(manifest.fact("meta.price_date.2026-10-01.CITED").raw_value),
                "equity_date": str(manifest.fact("meta.equity_date.FY2026.A-8K").raw_value),
                "shares_date": str(manifest.fact("meta.shares_date.CITED").raw_value),
            },
        )
        for locale in ("ko", "en"):
            run_gate(f"G-6 market data {locale}", gate_market_data_box, locale_configs[locale]["market_data"])
            html_text = outputs[f"html_{locale}"].read_text(encoding="utf-8")
            run_gate(
                f"G-8 theme {locale}",
                gate_theme,
                html_text,
                [(PACKAGE_DIR / "i18n" / "ko.yaml").read_text(encoding="utf-8"), (PACKAGE_DIR / "i18n" / "en.yaml").read_text(encoding="utf-8")],
            )
        run_gate("G-10 narrative contract", gate_narrative_contract, result["narrative"], manifest)
        run_gate("G-11 ed1 placeholders", gate_ed1_rendered, rendered_texts)
        run_gate("G-12b disclaimers", gate_g12b_disclaimers, rendered_texts)
        run_gate("G-12c conflict", gate_g12c_conflict, conflict, "ed1", render_started, state["rendered_conflict"])
        for locale in ("ko", "en"):
            charts = chart_manifests[locale]
            run_gate(f"G-13 charts {locale}", gate_g13_charts, charts)
            run_gate(f"G-13b chart identity {locale}", gate_g13b_chart_identity, manifest, charts)
            run_gate(f"G-13c chart semantics {locale}", gate_g13c_chart_semantics, manifest, charts)
        run_gate("G-15 parity", gate_g15_parity, references, manifest, rendered_texts)
        run_gate("G-15b localized UI", gate_g15b_localized_ui, chart_manifests, rendered_texts)
        availability_audit = run_gate("G-23 availability audit", gate_g23_availability, manifest, chart_manifests, rendered_texts)
        run_gate(
            "G-24 PDF/XLSX markup and labels",
            gate_g24_raw_markup,
            {locale: state["rendered_conflict"][locale]["pdf_pages"] for locale in ("ko", "en")},
            outputs["xlsx"],
        )
        run_gate("G-25 cover dates", gate_g25_cover_dates, rendered_texts)
        for locale in ("ko", "en"):
            for chart_id, chart in chart_manifests[locale].items():
                run_gate(f"G-16 caption {locale}/{chart_id}", gate_g16_caption, chart["caption"])
            run_gate(f"G-17 labels {locale}", gate_g17_labels, rendered_texts[locale], locale)
            run_gate(f"G-17b consensus {locale}", gate_g17b_consensus, references[locale], manifest)
        run_gate("G-17 corrected net-cash label", gate_g17_net_cash_label, locale_configs)
        text_outputs = [
            *[outputs[f"md_{locale}"] for locale in ("ko", "en")],
            *[outputs[f"html_{locale}"] for locale in ("ko", "en")],
            outputs["manifest"],
            outputs["input_manifest"],
        ]
        run_gate("G-18 hygiene", gate_g18_hygiene, text_outputs)
        run_gate("G-21 formats", gate_g21_formats, outputs)
        runtime_path = state["runtime_log"]
        runtime_payload = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime_payload["g23_availability_audit"] = availability_audit
        atomic_write(runtime_path, (json.dumps(runtime_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        payload = {
            "phase": "E2B",
            "status": "PASS" if not failures else "GATE_FAILURES_NO_FIX",
            "render_started_at_kst": render_started.isoformat(),
            "conflict_blob_sha": conflict.git_blob_sha,
            "outputs": {key: str(path.relative_to(REPO_ROOT)).replace("\\", "/") for key, path in outputs.items()},
            "passes": sorted(passes),
            "failures": failures,
            "runtime_log": str(state["runtime_log"].relative_to(REPO_ROOT)).replace("\\", "/"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not failures else 3
    if args.phase != "E2-A" or args.edition == "dryrun":
        parser.error("only E2-A is authorized in this implementation stage")
    build_sources(write_runtime_log=True)
    if args.output_dir:
        resolved = args.output_dir.resolve()
        reports = (Path(__file__).resolve().parents[2] / "reports").resolve()
        if resolved == reports or reports in resolved.parents:
            parser.error("E2-A cannot write under forecast/reports")
        render_fixture_bundle(fixture_manifest(), resolved)
    else:
        with tempfile.TemporaryDirectory(prefix="mu-report-e2a-") as directory:
            render_fixture_bundle(fixture_manifest(), directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
