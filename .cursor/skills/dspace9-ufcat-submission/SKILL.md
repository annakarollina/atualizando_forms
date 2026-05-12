---
name: dspace9-ufcat-submission
description: >-
  Edita configuração de submissão DSpace 9 (UFCAT): item-submission.xml, submission-forms.xml,
  Messages_pt_BR.properties e mapeamento de coleções. Usar quando o utilizador mencionar submissão,
  deposito, TEDE, TCC, dissertação, tese, submission-map, submission-process, DescribeStep,
  submission-forms ou DSpace 9 neste repositório atualizando_forms.
disable-model-invocation: true
---

# Submissão DSpace 9 — UFCAT (atualizando_forms)

## Antes de editar

1. Ler [AGENTS.md](../../../AGENTS.md) na raiz do repositório (versão 9, contratos XML, anti-padrões).
2. Confirmar que a alteração pedida é **config** (XML/properties), não código Java do DSpace — este repo é pacote de configuração.

## Checklist obrigatório após mudar fluxos

- [ ] Cada `collection-handle` (ou `default`) em `<submission-map>` aponta para um `submission-name` existente em `<submission-process>`.
- [ ] Cada `<step id="...">` no processo tem `<step-definition id="...">` com a mesma id.
- [ ] Passos `DescribeStep` (`submission-form`): existe `<form name="...">` em `submission-forms.xml` com **nome igual** ao id do passo.
- [ ] Headings novos: existe chave `submission.sections.{heading}` em `Messages_pt_BR.properties` (padrão REST Angular).
- [ ] Metadados novos em campos de formulário: checklist para **registro na instância** (fora deste repo) antes de considerar o fluxo completo no servidor.
- [ ] Atualizar [`docs/handles_UFCAT_Mapeamento.csv`](../../../docs/handles_UFCAT_Mapeamento.csv) se handles ou nomes de processo mudarem.

## Onde está cada coisa

| Objetivo | Ficheiro |
|----------|----------|
| Mapear coleção → processo | `item-submission.xml` → `<submission-map>` → `<name-map collection-handle="..." submission-name="..."/>` |
| Ordem dos passos / nomes dos processos | `item-submission.xml` → `<submission-process>` + `<step id="..."/>` |
| Partilhar definição de passo | `item-submission.xml` → `<step-definitions>` |
| Campos e tipos de input | `submission-forms.xml` → `<form name="idDoPasso">` |
| Rótulos PT no deposito REST | `Messages_pt_BR.properties` |

## Boas práticas DSpace 9 (resumo)

- Não misturar documentação **JSPUI** (`jsp.*`) com **REST/UI Angular** (`submit.*`, `submission.sections.*`) ao escolher chaves para o mesmo ecrã.
- `traditional` é o processo mapeado em `default`; coleções UFCAT sem `name-map` herdariam fluxo errado — evitar buracos no mapa.
- Value-pairs (`<pair>`) referenciados por `value-pairs-name` têm de existir no mesmo `submission-forms.xml` (ou ficheiro incluído, se a instalação usar includes).

## Referências externas

- Backend: [github.com/dspace/dspace](https://github.com/dspace/dspace) — pasta `config/` da tag/branch **9.x** usada em produção.
- Frontend: [github.com/DSpace/dspace-angular](https://github.com/DSpace/dspace-angular) — mesma linha de versão que o backend.

## Output esperado do agente

- Alterações **mínimas** ao pedido; não refatorar processos não mencionados.
- Se faltar contexto (ex.: qual minor 9.x ou política de metadados), perguntar em vez de assumir API antiga.
