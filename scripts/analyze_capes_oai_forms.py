#!/usr/bin/env python3
"""
Analisa submission-forms.xml e item-submission.xml para comparar com o CSV do guia CAPES.

O ficheiro oficial no repositório é capes_oai_guide_reference.csv na raiz (separador ';'):
  Nome do Metadado; Termo semântico; Exemplo de Metadados;

A coluna "Exemplo de Metadados" pode listar vários campos DSpace (dc.* ou universidade.*).

Uso:
  python3 scripts/analyze_capes_oai_forms.py [--guide PATH]

Saídas em docs/generated/:
  - forms_inventory.csv
  - submission_process_forms.csv
  - coverage_matrix.csv
  - coverage_gaps_report.txt
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FORMS_XML = ROOT / "submission-forms.xml"
SUBMISSION_XML = ROOT / "item-submission.xml"
OUT_DIR = ROOT / "docs" / "generated"
# CSV oficial na raiz do repositório (formato CAPES com ';')
DEFAULT_GUIDE = ROOT / "capes_oai_guide_reference.csv"  # raiz do repo (formato CAPES com ';')


def norm_qual(q: str | None) -> str:
    return (q or "").strip()


def triplet_key(schema: str, element: str, qualifier: str) -> str:
    q = norm_qual(qualifier)
    return f"{schema}.{element}.{q if q else '_'}"


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


_DC_TOKEN = re.compile(r"\bdc\.([a-zA-Z0-9]+)(?:\.([a-zA-Z0-9\-]+))?\b")


def parse_dc_triplets_from_exemplo(cell: str) -> list[str]:
    """Extrai triplets dc.*.* da coluna 'Exemplo de Metadados' do guia CAPES."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _DC_TOKEN.finditer(cell or ""):
        elem, qual = m.group(1), m.group(2) or ""
        key = triplet_key("dc", elem, qual)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def is_section_header_row(label: str, semantic: str, exemplo: str) -> bool:
    t = (label + semantic + exemplo).lower()
    if "nome do metadado" in label.lower() and "termo semântico" in semantic.lower():
        return True
    if "nota técnica" in t or "notas técnicas" in t:
        return True
    if "destaca-se" in t and "dcterms:abstract" in t:
        return True
    return False


def load_capes_guide(path: Path) -> list[dict[str, str]]:
    """
    Lê o CSV CAPES (delimiter ';') ou o formato legado (delimiter ',' com dc_element).
    Cada item devolvido tem: capes_label, semantic_term, exemplo_metadados, dc_triplets (lista em string '|').
    """
    raw = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(raw[:4096], delimiters=";,\t")
    reader = csv.DictReader(raw.splitlines(), delimiter=dialect.delimiter)
    fieldnames = reader.fieldnames or []
    # Normalizar nomes de colunas
    fn_lower = { (n or "").strip().lower(): n for n in fieldnames }

    rows_out: list[dict[str, str]] = []

    if "dc_element" in fn_lower:
        # Formato legado compacto
        for row in reader:
            r = {k: (v or "").strip() for k, v in row.items()}
            el = r.get("dc_element", "")
            qual = r.get("dc_qualifier", "")
            keys = []
            if el:
                keys.append(triplet_key("dc", el, qual))
            rows_out.append(
                {
                    "capes_label": r.get("capes_label", ""),
                    "semantic_term": "",
                    "exemplo_metadados": "",
                    "obligation": r.get("obligation", ""),
                    "notes": r.get("notes", ""),
                    "dc_triplets": "|".join(keys),
                }
            )
        return rows_out

    # Formato oficial CAPES
    key_label = fn_lower.get("nome do metadado") or fn_lower.get("nome_do_metadado")
    key_sem = fn_lower.get("termo semântico") or fn_lower.get("termo semantico")
    key_ex = fn_lower.get("exemplo de metadados") or fn_lower.get("exemplo_de_metadados")

    if not key_label or not key_ex:
        raise ValueError(
            f"CSV do guia sem colunas esperadas. Encontrado: {fieldnames}. "
            "Use ';' com Nome do Metadado; Termo semântico; Exemplo de Metadados;"
        )

    for row in reader:
        r = {k: (v or "").strip() for k, v in row.items()}
        label = r.get(key_label, "") if key_label else ""
        semantic = r.get(key_sem, "") if key_sem else ""
        exemplo = r.get(key_ex, "") if key_ex else ""

        if not label and not exemplo:
            continue
        if is_section_header_row(label, semantic, exemplo):
            continue
        triplets = parse_dc_triplets_from_exemplo(exemplo)
        rows_out.append(
            {
                "capes_label": label,
                "semantic_term": semantic,
                "exemplo_metadados": exemplo,
                "obligation": "",
                "notes": "",
                "dc_triplets": "|".join(triplets),
            }
        )

    return rows_out


# Um triplet do guia pode ser coberto por variantes nos formulários.
EQUIVALENT_FORM_TRIPLETS: dict[str, frozenset[str]] = {
    "dc.contributor.author": frozenset({"dc.contributor.author", "dc.creator._"}),
    "dc.language.iso": frozenset({"dc.language.iso", "dc.language._"}),
    "dc.description.abstract": frozenset(
        {"dc.description.abstract", "dc.description.resumo"}
    ),
    # Guia pode citar dc.relation.none; em DSpace costuma ser qualifier vazio
    "dc.relation.none": frozenset({"dc.relation.none", "dc.relation._"}),
}


def process_has_guide_field(triplets: set[str], guide_key: str) -> bool:
    if guide_key in triplets:
        return True
    equiv = EQUIVALENT_FORM_TRIPLETS.get(guide_key)
    if equiv:
        return bool(equiv & triplets)
    return False


def row_matches_guide_row(triplets: set[str], guide_keys: list[str]) -> bool:
    """No guia CAPES, vários dc.* na mesma célula são alternativas (OR), não todos obrigatórios."""
    if not guide_keys:
        return False
    return any(process_has_guide_field(triplets, k) for k in guide_keys)


def obligation_is_mandatory(ob: str) -> bool:
    ob = (ob or "").upper().strip()
    return bool(ob) and ob.startswith("M") and ob != "O"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--guide",
        type=Path,
        default=DEFAULT_GUIDE,
        help="CSV do guia (raiz: capes_oai_guide_reference.csv)",
    )
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

    proc_path = OUT_DIR / "submission_process_forms.csv"
    with proc_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["submission_process", "describe_form_steps_in_order"])
        for pname, forms in processes:
            w.writerow([pname, " | ".join(forms)])

    guide_rows: list[dict[str, str]] = []
    if args.guide.exists():
        try:
            guide_rows = load_capes_guide(args.guide)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
    else:
        print(f"Guide CSV not found: {args.guide}", file=sys.stderr)

    def triplets_for_process(forms: list[str]) -> set[str]:
        acc: set[str] = set()
        for fn in forms:
            acc |= form_triplets.get(fn, set())
        return acc

    focus_prefixes = (
        "traditional",
        "dissertation",
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

    proc_map = dict(processes)

    matrix_path = OUT_DIR / "coverage_matrix.csv"
    with matrix_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "capes_label",
                "semantic_term",
                "dc_triplets_from_guide",
                "obligation_guide",
                "covered_traditional",
                "covered_dissertationProcess",
                "covered_thesisProcess",
                "covered_tccProcess",
                "covered_openairePublicationSubmission",
            ]
        )
        for row in guide_rows:
            keys_str = row.get("dc_triplets", "")
            gkeys = [k for k in keys_str.split("|") if k]
            if not gkeys:
                continue
            obl = row.get("obligation", "")

            def cov(name: str) -> str:
                triplets = triplets_for_process(proc_map.get(name, []))
                return "yes" if row_matches_guide_row(triplets, gkeys) else "no"

            w.writerow(
                [
                    row.get("capes_label", ""),
                    row.get("semantic_term", ""),
                    keys_str,
                    obl,
                    cov("traditional"),
                    cov("dissertationProcess"),
                    cov("thesisProcess"),
                    cov("tccProcess"),
                    cov("openairePublicationSubmission"),
                ]
            )

    report_path = OUT_DIR / "coverage_gaps_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("Relatório gerado por analyze_capes_oai_forms.py\n")
        f.write(f"Guia: {args.guide}\n\n")
        if not args.guide.exists():
            f.write("AVISO: CSV do guia não encontrado.\n\n")

        f.write(
            "Linhas do guia (OR entre dc.* da mesma célula) onde nenhum triplet "
            "está presente no formulário do processo:\n\n"
        )
        for row in guide_rows:
            keys_str = row.get("dc_triplets", "")
            gkeys = [k for k in keys_str.split("|") if k]
            if not gkeys:
                continue
            missing_detail: list[str] = []
            for pname, fs in selected:
                tset = triplets_for_process(fs)
                if not row_matches_guide_row(tset, gkeys):
                    missing_detail.append(
                        f"{pname}: nenhum de {', '.join(gkeys)}"
                    )
            if missing_detail:
                f.write(f"- {row.get('capes_label', '')[:120]}\n")
                f.write(f"  Triplets guia: {keys_str}\n")
                for line in missing_detail[:25]:
                    f.write(f"  · {line}\n")
                if len(missing_detail) > 25:
                    f.write(f"  · ... e mais {len(missing_detail) - 25} processos\n")
                f.write("\n")

        f.write("\nTriplets não-DC nos formulários (amostra):\n")
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
