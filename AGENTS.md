# AGENTS.md — UFCAT / submissão DSpace 9

Orientação para humanos e para agentes de IA que editam **configuração de submissão** neste repositório.

## Versão e fonte de verdade

- **Alvo:** DSpace **9.x**. Não assumir comportamento de DSpace 6/7 ou JSPUI sem confirmar na documentação **da mesma major** (9).
- **Em caso de conflito:** prevalece a documentação e o código da release **DSpace 9.x** em [dspace/dspace](https://github.com/dspace/dspace) (incluindo `config/`) até este repositório ser atualizado explicitamente.
- **Frontend de referência:** [DSpace/dspace-angular](https://github.com/DSpace/dspace-angular) na branch/versão alinhada ao backend 9.

### Este repositório vs. servidor (homolog / produção)

- **`submission-forms.xml` e `item-submission.xml` aqui não são, por si só, a “fonte da verdade” do que está no ar:** são o pacote em que se **melhora** a configuração; o repositório homologação (`repositorio.homolog.ufcat.edu.br`, etc.) só fica alinhado **depois** do TI aplicar os ficheiros e reiniciar/recarregar conforme prática local.
- **TCC e COAR:** se no homolog o passo “TCC: Direitos” mostrar o dropdown de acesso com **“Acesso a metadados”** (vocabulário COAR, URI `c_14cb`), isso pode reflectir **deploy ou ajuste feito pelo próprio TI** no servidor, e não obrigatoriamente o último estado deste Git — ao diagnosticar diferenças, comparar ficheiros no backend com o repo, não assumir culpa só do XML local.
- **`dc.subject.cnpq`:** o campo com **árvore hierárquica** (modal “Visualização de árvore hierárquica”, vocabulário `cnpq`) **só funciona** com o ficheiro de vocabulário correspondente (**`cnpq.xml` ou equivalente**) presente no servidor. **Prova em homolog:** com esse ficheiro instalado, a UI lista as grandes áreas CNPq (ex.: CIÊNCIAS EXATAS E DA TERRA, ENGENHARIAS, …) — ou seja, confirma que o binding `dc.subject.cnpq` + vocabulário está operacional no ambiente onde foi testado.

## Ficheiros centrais

| Ficheiro | Função |
|----------|--------|
| [`item-submission.xml`](item-submission.xml) | `<submission-map>`: `name-map` (handle da coleção → `submission-name`). `default` → `traditional`. Definição de `<submission-process>` e `<step-definition>`. |
| [`submission-forms.xml`](submission-forms.xml) | `<form name="...">` deve coincidir com o `id` do passo `DescribeStep` referenciado no processo. |
| [`Messages_pt_BR.properties`](Messages_pt_BR.properties) | Rótulos de secção no UI REST: `submission.sections.{heading}` quando o `<heading>` no passo for, por exemplo, `tcc.identification`. |
| [`docs/handles_UFCAT_Mapeamento.csv`](docs/handles_UFCAT_Mapeamento.csv) | Mapeamento de handles de coleções (homologação / planeamento); manter coerente com o `submission-map`. |

## Contratos (evitar erros comuns)

1. **`submission-name`** em `<name-map>` tem de existir como `<submission-process name="...">`.
2. Cada `<step id="X">` exige `<step-definition id="X">`. Para `DescribeStep`, o formulário em `submission-forms.xml` usa `<form name="X">` com o **mesmo** `X`.
3. **Headings:** preferir chaves estáveis (`dissertation.*`, `thesis.*`, `tcc.*`) e traduzir em `Messages_pt_BR.properties`. Repetir `submit.progressbar.describe.stepone` em vários passos gera **rótulos duplicados** no progresso.
4. **Metadados:** qualificadores `dc.*` custom só depois de existirem no **registro de metadados** da instância DSpace; caso contrário o REST pode omitir campos.
5. **Palavras-chave PT / EN:** dois campos **`dc.subject`** (sem qualificador), repetíveis, com **idioma fixo por coluna**: **`<language value-pairs-name="ufcat_subject_lang_por">true</language>`** e **`ufcat_subject_lang_eng`** (listas de um só par `por` / `eng` em `form-value-pairs`). Distinto de **`dc.language`**, que descreve o idioma principal da obra.

## Anti-padrões neste projeto

- **Removido:** processos duplicados `dissProcess_*` / `thesisProcess_*` e formulários monolíticos por programa; mestrado usa só `dissertationProcess`, doutorado só `thesisProcess`.
- **Deploy:** registar no DSpace os qualificadores `dc.contributor.referee1Lattes` … `referee5Lattes` (espelho de `advisor1Lattes`) antes de exigir esses campos em produção.

## Deploy

- Envio dos XMLs/properties ao **departamento TI** da universidade (e-mail / processo interno); eles aplicam no **backend** e reiniciam ou recarregam config conforme prática local.
- Após alterar processos ou mapas: validar no UI pelo menos **uma** coleção por fluxo (ex.: TCC, mestrado, doutorado).

## Não fazer

- Criar `<submission-process>` novo sem entrada correspondente em `<submission-map>` (ou sem plano para `name-map`).
- Remover um `<submission-process>` ainda referenciado por `submission-name` em qualquer `name-map`.

## Regra Cursor (automática nos XML)

Com `item-submission.xml` ou `submission-forms.xml` abertos ou em foco, o Cursor carrega [.cursor/rules/dspace9-submission-xml.mdc](.cursor/rules/dspace9-submission-xml.mdc) (resumo + ligação a este ficheiro).

## Skill Cursor (opcional)

Para checklist longo ou quando quiseres invocar explicitamente: **dspace9-ufcat-submission** (`.cursor/skills/dspace9-ufcat-submission/`).
