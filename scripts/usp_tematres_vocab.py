#!/usr/bin/env python3
"""
Cliente mínimo para o serviço web TemaTres do Vocabulário Controlado da USP (ABCD/USP).

Base documental: https://vocabulario.abcd.usp.br/pt-br/services.php
Parâmetros: task, arg (opcional), output=xml|json (XML por omissão no servidor).

Exemplos de linha de comandos:

  # Metadados do vocabulário
  python scripts/usp_tematres_vocab.py --task fetchVocabularyData -o vocab_meta.xml

  # Termos de topo
  python scripts/usp_tematres_vocab.py --task fetchTopTerms -o top.xml

  # Ramo descendente a partir de um term_id (XML bruto)
  python scripts/usp_tematres_vocab.py --task fetchDown --arg 101833 -o down_101833.xml

  # Percorrer fetchDown em largura (use --delay para não sobrecarregar o serviço)
  python scripts/usp_tematres_vocab.py --crawl-down --root 101833 --out-dir out_usp_branch --max-requests 500 --delay 0.25

Uso como biblioteca (com o repositório como cwd, ou com `scripts/` no PYTHONPATH):

  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path("scripts").resolve()))
  from usp_tematres_vocab import UspTematresClient
  client = UspTematresClient()
  xml_bytes = client.fetch_xml("fetchTopTerms")
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

DEFAULT_SERVICES_URL = "https://vocabulario.abcd.usp.br/pt-br/services.php"
DEFAULT_TIMEOUT_S = 120
DEFAULT_USER_AGENT = "atualizando_forms-usp_tematres_vocab/1.0 (+https://github.com/dspace)"


class UspTematresClient:
    """Chamadas HTTP ao endpoint `services.php` da instância USP (TemaTres)."""

    def __init__(
        self,
        services_url: str = DEFAULT_SERVICES_URL,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.services_url = services_url.rstrip()
        self.timeout_s = timeout_s
        self.user_agent = user_agent

    def build_url(self, task: str, arg: str | None = None, *, output: str = "xml") -> str:
        q: dict[str, str] = {"task": task, "output": output}
        if arg is not None and arg != "":
            q["arg"] = arg
        return f"{self.services_url}?{urllib.parse.urlencode(q)}"

    def fetch_raw(
        self,
        task: str,
        arg: str | None = None,
        *,
        output: str = "xml",
    ) -> bytes:
        url = self.build_url(task, arg, output=output)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read() if hasattr(e, "read") else b""
            raise RuntimeError(f"HTTP {e.code} em {url}: {body[:500]!r}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Falha de rede em {url}: {e}") from e

    def fetch_xml(self, task: str, arg: str | None = None) -> bytes:
        return self.fetch_raw(task, arg, output="xml")

    def fetch_json(self, task: str, arg: str | None = None) -> bytes:
        return self.fetch_raw(task, arg, output="json")


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text.strip()


def parse_term_ids_from_result(xml_bytes: bytes) -> list[str]:
    """Extrai `term_id` de todos os `<term>` dentro de `<result>` (útil após fetchTopTerms / fetchDown)."""
    root = ET.fromstring(xml_bytes)
    out: list[str] = []
    for term in root.findall(".//result/term"):
        tid = _text(term.find("term_id"))
        if tid:
            out.append(tid)
    return out


def crawl_fetch_down(
    client: UspTematresClient,
    root_ids: list[str],
    out_dir: Path,
    *,
    delay_s: float = 0.0,
    max_requests: int | None = None,
) -> int:
    """
    Para cada term_id em fila, grava `fetchDown` em `out_dir/{id}.xml` e enfileira filhos
    encontrados no mesmo `<result>`. Evita ciclos com conjunto `visited`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    visited: set[str] = set()
    queue: list[str] = list(root_ids)
    n = 0
    while queue:
        tid = queue.pop(0)
        if tid in visited:
            continue
        visited.add(tid)
        if max_requests is not None and n >= max_requests:
            break
        xml_bytes = client.fetch_xml("fetchDown", tid)
        (out_dir / f"{tid}.xml").write_bytes(xml_bytes)
        n += 1
        for child in parse_term_ids_from_result(xml_bytes):
            if child not in visited:
                queue.append(child)
        if delay_s > 0:
            time.sleep(delay_s)
    return n


def _parse_root_ids(s: str) -> list[str]:
    parts = [p.strip() for p in s.replace(",", " ").split() if p.strip()]
    return parts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cliente XML/JSON para services.php (Vocabulário USP / TemaTres).")
    p.add_argument("--base-url", default=DEFAULT_SERVICES_URL, help="URL completa de services.php")
    p.add_argument("--task", default="fetchVocabularyData", help="Nome da task TemaTres (ex.: fetchTopTerms, fetchDown)")
    p.add_argument("--arg", default=None, help="Argumento da task (string ou IDs separados por vírgula)")
    p.add_argument("--output-format", choices=("xml", "json"), default="xml")
    p.add_argument("-o", "--out", type=Path, default=None, help="Ficheiro de saída (stdout se omitido)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)

    p.add_argument(
        "--crawl-down",
        action="store_true",
        help="Em vez de uma única chamada, percorre fetchDown a partir de --root (vários pedidos).",
    )
    p.add_argument(
        "--root",
        default=None,
        help="term_id inicial(is) para --crawl-down (vários: '101833 102307' ou '101833,102307'). "
        "Se omitido com --crawl-down, usa term_ids devolvidos por fetchTopTerms.",
    )
    p.add_argument("--out-dir", type=Path, default=Path("usp_vocab_fetchdown"), help="Pasta para XML por term_id")
    p.add_argument("--delay", type=float, default=0.2, help="Pausa em segundos entre pedidos no crawl")
    p.add_argument("--max-requests", type=int, default=None, help="Limite de pedidos no crawl (segurança)")

    args = p.parse_args(argv)

    client = UspTematresClient(args.base_url, timeout_s=args.timeout)

    if args.crawl_down:
        if args.root:
            roots = _parse_root_ids(args.root)
        else:
            top = client.fetch_xml("fetchTopTerms")
            roots = parse_term_ids_from_result(top)
            if not roots:
                print("fetchTopTerms não devolveu term_ids.", file=sys.stderr)
                return 2
        n = crawl_fetch_down(
            client,
            roots,
            args.out_dir,
            delay_s=args.delay,
            max_requests=args.max_requests,
        )
        print(f"Gravados {n} ficheiros XML em {args.out_dir.resolve()}")
        return 0

    body = client.fetch_raw(args.task, args.arg, output=args.output_format)
    if args.out:
        args.out.write_bytes(body)
        print(str(args.out.resolve()))
    else:
        # Consola pode corromper UTF-8 em Windows; ainda assim útil para inspeção rápida
        sys.stdout.buffer.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
