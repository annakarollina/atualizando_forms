#!/usr/bin/env python3
"""
Analisa submission-forms.xml e item-submission.xml para comparar com CSV do guia OAI CAPES.

Uso:
  python3 scripts/analyze_capes_oai_forms.py [--guide PATH]

Saídas em docs/generated/:
  - forms_inventory.csv
  - submission_process_forms.csv
  - coverage_matrix.csv (stub CSV vs processos chave)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FORMS_XML = ROOT / "submission-forms.xml"
SUBMISSION_XML = ROOT / "item-submission.xml"
OUT_DIR = ROOT / "docs" / "generated"
DEFAULT_GUIDE = ROOT / "docs" / "capes_oai_guide_reference.csv"


def norm_qual(q: str | None) -> str:
    return (q or "").strip()


def triplet_key(schema: str, element: str, qualifier: str) -> str:
    return f"{schema}.{element}.{norm_qual(qualifier) if norm_qual(qualifier) else '_'}"


def parse_submission_forms(path: Path) -> tuple[dict[str, set[str]], set[str]]:
    """Retorna (form_name -> set triplet keys), e conjunto global de triplets."""
    tree = ET.parse(path)
    root = tree.getroot()
    forms: dict[str, set[str]] = {}
    global_triplets: set[str] = set()

    def add_field(form_name: str, schema_el: ET.Element | None, elem_el: ET.Element | None, qual_el: ET.Element | None):
        if schema_el is None or elem_el is None:
            return
        schema = (schema_el.text or "").strip()
        element = (elem_el.text or "").strip()
        qualifier = norm_qual(qual_el.text if qual_el is not None else "")
        key = triplet_key(schema, element, qualifier)
        forms.setdefault(form_name, set()).add(key)
        global_triplets.add(key)

    for form in root.findall(".//form-definitions/form"):
        fname = form.get("name")
        if not fname:
            continue
        for field in form.findall(".//field"):
            add_field(
                fname,
                field.find("dc-schema"),
                field.find("dc-element"),
                field.find("dc-qualifier"),
            )
        for lmf in form.findall(".//linked-metadata-field"):
            add_field(
                fname,
                lmf.find("dc-schema"),
                lmf.find("dc-element"),
                lmf.find("dc-qualifier"),
            )

    return forms, global_triplets


def parse_form_steps(path: Path) -> set[str]:
    """IDs de steps do tipo submission-form."""
    tree = ET.parse(path)
    root = tree.getroot()
    out: set[str] = set()
    for step_def in root.findall(".//step-definitions/step-definition"):
        stype = step_def.find("type")
        if stype is not None and (stype.text or "").strip() == "submission-form":
            sid = step_def.get("id")
            if sid:
                out.add(sid)
    return out


def parse_submission_processes(path: Path, form_step_ids: set[str]) -> list[tuple[str, list[str]]]:
    """Lista (process_name, [form_names na ordem])."""
    tree = ET.parse(path)
    root = tree.getroot()
    processes: list[tuple[str, list[str]]] = []
    for proc in root.findall(".//submission-definitions/submission-process"):
        pname = proc.get("name")
        if not pname:
            continue
        forms_in_proc: list[str] = []
        for step in proc.findall("step"):
            sid = step.get("id")
            if sid and sid in form_step_ids:
                forms_in_proc.append(sid)
        processes.append((pname, forms_in_proc))
    return processes


def load_guide_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def dc_triplet_from_guide_row(row: dict[str, str]) -> str | None:
    el = row.get("dc_element", "").strip()
    if not el:
        return None
    qual = row.get("dc_qualifier", "").strip()
    return triplet_key("dc", el, qual)


# Campos do guia (chave dc.*) satisfeitos por mais de um triplet nos formulários ou no OAI.
EQUIVALENT_FORM_TRIPLETS: dict[str, frozenset[str]] = {
    # OAI-DC usa dc:creator; DSpace pode guardar dc.creator ou dc.contributor.author
    "dc.contributor.author": frozenset(
        {"dc.contributor.author", "dc.creator._"}
    ),
    # Idioma: qualificador iso vs campo language sem qualificador (valor ISO nas value-pairs)
    "dc.language.iso": frozenset({"dc.language.iso", "dc.language._"}),
    # Resumo: guia pode pedir abstract; UFCAT usa resumo PT em description.resumo
    "dc.description.abstract": frozenset(
        {"dc.description.abstract", "dc.description.resumo"}
    ),
}


def process_has_guide_field(triplets: set[str], guide_key: str) -> bool:
    if guide_key in triplets:
        return True
    equiv = EQUIVALENT_FORM_TRIPLETS.get(guide_key)
    if equiv:
        return bool(equiv & triplets)
    return False


def obligation_is_mandatory(ob: str) -> bool:
    ob = (ob or "").upper().strip()
    return ob.startswith("M") and "O" != ob  # M, MA count as needing coverage


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--guide", type=Path, default=DEFAULT_GUIDE, help="CSV do guia CAPES")
    args = ap.parse_args()

    if not FORMS_XML.exists():
        print(f"Missing {FORMS_XML}", file=sys.stderr)
        return 1
    if not SUBMISSION_XML.exists():
        print(f"Missing {SUBMISSION_XML}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    form_triplets, _ = parse_submission_forms(FORMS_XML)
    form_step_ids = parse_form_steps(SUBMISSION_XML)
    processes = parse_submission_processes(SUBMISSION_XML, form_step_ids)

    # Inventário por formulário
    inv_path = OUT_DIR / "forms_inventory.csv"
    with inv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["form_name", "schema", "element", "qualifier", "triplet"])
        for form_name in sorted(form_triplets.keys()):
            for t in sorted(form_triplets[form_name]):
                schema, rest = t.split(".", 1)
                elem, qual = rest.rsplit(".", 1)
                if qual == "_":
                    qual = ""
                w.writerow([form_name, schema, elem, qual, t])

    # Processos -> formulários
    proc_path = OUT_DIR / "submission_process_forms.csv"
    with proc_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["submission_process", "describe_form_steps_in_order"])
        for pname, forms in processes:
            w.writerow([pname, " | ".join(forms)])

    # Cobertura: guia DC vs união de triplets por processo
    guide_rows: list[dict[str, str]] = []
    if args.guide.exists():
        guide_rows = load_guide_csv(args.guide)
    else:
        print(f"Guide CSV not found: {args.guide}", file=sys.stderr)

    def triplets_for_process(forms: list[str]) -> set[str]:
        acc: set[str] = set()
        for fn in forms:
            acc |= form_triplets.get(fn, set())
        return acc

    # Processos de interesse UFCAT + tradicional + openaire
    focus_prefixes = (
        "traditional",
        "dissertation",
        "dissProcess",
        "thesisProcess",
        "tcc",
        "ordinance",
        "resolution",
        "policy",
        "administrative",
        "openaire",
        "Publication",
        "Dataset",
    )
    selected = [(p, fs) for p, fs in processes if any(p.startswith(pr) for pr in focus_prefixes)]

    matrix_path = OUT_DIR / "coverage_matrix.csv"
    with matrix_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "dc_element",
                "dc_qualifier",
                "obligation_guide",
                "capes_label",
                "triplet_key",
                "covered_traditional",
                "covered_dissertationProcess",
                "covered_thesisProcess",
                "covered_tccProcess",
                "covered_openairePublicationSubmission",
            ]
        )
        # Resolver processos por nome
        proc_map = dict(processes)
        for row in guide_rows:
            tkey = dc_triplet_from_guide_row(row)
            if not tkey:
                continue
            obl = row.get("obligation", "")
            label = row.get("capes_label", "")
            el = row.get("dc_element", "")
            qual = row.get("dc_qualifier", "")

            def cov(name: str) -> str:
                triplets = triplets_for_process(proc_map.get(name, []))
                return "yes" if process_has_guide_field(triplets, tkey) else "no"

            w.writerow(
                [
                    el,
                    qual,
                    obl,
                    label,
                    tkey,
                    cov("traditional"),
                    cov("dissertationProcess"),
                    cov("thesisProcess"),
                    cov("tccProcess"),
                    cov("openairePublicationSubmission"),
                ]
            )

    # Relatório texto: lacunas M para processos selecionados
    report_path = OUT_DIR / "coverage_gaps_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("Relatório gerado por analyze_capes_oai_forms.py\n\n")
        if not args.guide.exists():
            f.write("AVISO: CSV do guia não encontrado; matriz pode estar vazia.\n\n")
        f.write("Campos do guia (dc.*) ausentes por processo (apenas obligation M ou MA):\n\n")
        for row in guide_rows:
            obl = row.get("obligation", "")
            if not obligation_is_mandatory(obl):
                continue
            tkey = dc_triplet_from_guide_row(row)
            if not tkey:
                continue
            missing = [
                p
                for p, fs in selected
                if not process_has_guide_field(triplets_for_process(fs), tkey)
            ]
            if missing:
                f.write(
                    f"- {tkey} ({row.get('capes_label','')}) obr={obl} ausente em: {', '.join(missing)}\n"
                )

        f.write("\n\nTriplets não-DC nos formulários (amostra; podem mapear OAI via crosswalk):\n")
        non_dc = sorted({t for fts in form_triplets.values() for t in fts if not t.startswith("dc.")})
        for t in non_dc[:80]:
            f.write(f"  {t}\n")
        if len(non_dc) > 80:
            f.write(f"  ... e mais {len(non_dc) - 80} triplets\n")

    print(f"Wrote {inv_path}")
    print(f"Wrote {proc_path}")
    print(f"Wrote {matrix_path}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
