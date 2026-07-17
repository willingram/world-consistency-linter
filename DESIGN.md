# Design decisions and compatibility contract

## Product and trust boundary

One invocation loads one local manifest, reads the local files it names,
extracts text and metadata into in-memory chunks, derives mentions and findings,
and writes three reports. WCL is a deterministic screening aid for
cross-document seams, not proof that a document bundle is consistent, authentic,
safe, or complete.

The supported entry points are `wcl`, `world-consistency-linter`, and
`python -m world_consistency_linter`. They share one parser and behavior.
`--manifest` and `--out` are required. `--fail-on` accepts `GLANCE`,
`STANDARD`, or `DEEP` in the exact uppercase or lowercase spellings exposed by
CLI help.

The WCL runtime makes no deliberate network requests, starts no subprocesses,
and does not call an LLM. Parser libraries remain part of the trust boundary.

## Manifest and path authority

The manifest is read as UTF-8 and loaded with `yaml.safe_load`. Its root must be
a mapping, but it is not validated against a published schema. Some malformed
values produce a controlled manifest error; others may be ignored, coerced to
strings, or fail later. Unknown top-level data is retained in the in-memory
`raw` mapping but is not thereby interpreted.

Recognized declarations are:

- `files`: strings or mappings with required `path` and optional
  `purported_author`, `purported_org`, `purported_date`, `independent_of`, and
  `chronological`;
- `entities.people`: names, aliases, and optional title/organisation canon;
- `entities.orgs`: names, aliases, and optional address/phone canon;
- `entities.ids`: string IDs or mappings with optional kind/description;
- `doc_graph`: declared `from`/`cites` relationships;
- `intended_findings`: text used by the intended-finding matcher;
- `stopwords`: additions to name-extraction stopwords; and
- `unique_titles`: titles that should have one holder within an organisation.

Relative input paths resolve from the manifest directory. Absolute paths and
paths that escape that directory are also accepted. Resolution follows normal
filesystem semantics and is not confined to a bundle root, so a manifest has
the authority to request any file readable by the running account.

The output path is interpreted from the caller's working directory when it is
relative. WCL creates that directory and replaces three fixed report files
inside it. There is no output-root containment rule or transactional
multi-report publication.

## Format and extraction boundary

Every declared input contributes a filename chunk. WCL then dispatches by
lower-cased suffix:

- `.txt`, `.md`, `.json`, `.yaml`, and `.yml` are decoded as UTF-8 text with
  replacement for invalid bytes; JSON and YAML document inputs are not parsed
  structurally;
- `.csv` and `.tsv` use Python's CSV reader and become one row-labelled chunk;
- `.pdf` is parsed independently by pdfplumber and pypdf, page by page, with
  PDF metadata added when available; differing normalized text is reported as
  an extractor disagreement, while no text from either parser marks the file
  image-only;
- `.docx` contributes paragraphs, tables, headers, footers, and text stripped
  heuristically from comment, footnote, and endnote XML parts;
- `.pptx` contributes text from slide shapes and notes-slide shapes; and
- `.xlsx`, `.xlsm`, and `.xls` are dispatched to openpyxl with formulas exposed
  as formula text (`data_only=False`), plus sheet names, visible/hidden sheet
  rows, defined names, and selected workbook properties.

The base dependencies support modern OOXML workbooks. Legacy binary `.xls`
files are dispatched to the workbook backend but are not a reliable supported
input and normally become controlled unreadable-file errors. An unrecognized
suffix falls back to UTF-8 text extraction rather than being rejected.
WCL invokes no optional parser plugins or external system executables; parsing
behavior is determined by the installed Python dependencies.

Manifest author, organisation, and date declarations become a separate
manifest channel. Parser exceptions become hard input errors. A non-image file
with no content chunk is an empty-extraction error. An image-only PDF is
reported but is not itself a hard error.

WCL performs no OCR and does not promise extraction of images, embedded
objects, tracked changes, every OOXML part, spreadsheet cached formula results,
macros, or active content. It does not evaluate formulas or macros, fetch
external links, sanitize containers, or make malformed documents safe.

## Mention and check pipeline

Chunks are processed in manifest order. Pattern extraction derives declared
entity references, title/name pairs, candidate people, email addresses, phone
numbers, postal-style addresses, IDs, dates, timestamps, weekday/date
mismatches, and ambiguous dates or aliases. Regexes and proximity windows are
conservative heuristics; omission and false positives are expected.

Checks currently cover:

- person-title canon conflicts and multiple observed titles;
- singular-role collisions and titled people missing from declared people
  canon;
- declared and phrase-derived future citations;
- timestamp monotonicity for explicitly or heuristically chronological files;
- calendar truth and ambiguous date/person notes;
- organisation-address canon conflicts and manifest-vs-file metadata;
- repeated incidental addresses or phone numbers across files treated as
  independent; and
- repeated eight-word phrasing across files attributed to different authors.

The check list, titles, evidence, and heuristics are compatibility-sensitive,
not a complete ontology of document consistency.

## Canon, intention, and independence

Canon enriches checks; it does not validate the manifest itself or prove the
truth of declared facts. Names and aliases are matched case-insensitively with
word boundaries. Some short aliases are retained as ambiguous rather than
merged. Organisation names also extend the name-extraction stopword set.

Findings begin as `UNINTENDED`. Each `intended_findings` string is compared
case-insensitively against the finding's check ID, title, and summary using a
substring heuristic in either direction. A match changes the classification to
`INTENDED`; it is not proof of intent and it does not remove the finding from
reports.

Independence is also heuristic. An explicit `independent_of` declaration in
either direction can establish independence. A shared non-empty purported
author or organisation can suppress independence; absent such evidence, files
are generally treated as independent. The current multi-file helper is
pairwise and short-circuits on its first decisive pair, so it should not be
treated as a general provenance model.

## Loudness, thresholds, and exits

Loudness is an analyst-visibility rank, not impact, confidence, or security
severity:

- `GLANCE` is most visible and has rank 3;
- `STANDARD` has rank 2; and
- `DEEP` is least visible and has rank 1.

Only `UNINTENDED` findings participate in failure thresholds. The tested matrix
is:

- `--fail-on glance` fails `GLANCE` only;
- the default `--fail-on standard` fails `GLANCE` and `STANDARD`; and
- `--fail-on deep` fails all three loudness levels.

A controlled run returns `0` when no unintended finding reaches the selected
threshold, `2` when at least one does, and `3` for manifest or extraction/input
errors. Hard input errors take precedence over findings and remain exit `3`
under every threshold. Argparse also uses exit `2` for usage errors. Unexpected
check/report-writing failures are not converted into structured results and may
produce an interpreter traceback and another non-zero exit.

## Report and determinism contract

WCL writes:

- `worldlint_report.md`, with hard errors, image-only inputs, extractor
  disagreements, and findings sorted with unintended findings first and louder
  findings before quieter ones;
- `worldlint_report.json`, containing the resolved manifest path, extraction
  diagnostics, and finding objects; and
- `entity_index.md`, grouping mentions by kind and listing previews of every
  extracted chunk.

Reports can contain source text, metadata, entity details, filenames, and local
absolute paths. Evidence is deduplicated for Markdown presentation, while JSON
retains the finding objects produced by the pipeline. The three files are
written sequentially and non-atomically; unrelated existing files in the output
directory are left in place.

There is no randomness in WCL's own pipeline, and report ordering is deliberate.
Repeatability assumes the same input bytes, manifest, paths, Python/runtime
environment, and parser dependency versions. Byte-for-byte equality across
dependency versions or operating systems is not promised because third-party
document parsers and source metadata can vary.

## Distribution and fixture contract

The distributable artifacts are one pure-Python wheel and one source
distribution. The wheel contains runtime package code, metadata, entry points,
and the license. The source distribution additionally contains project
documentation, public examples, all tests, the complete small synthetic
PDF/DOCX/XLSX/CSV/YAML fixture corpus, and the distribution inspector so it can
rebuild and test independently.

`scripts/inspect_distribution.py` checks required members, exact entry points,
metadata, archive path safety, and common secret/development residue. It is a
release preflight, not a general archive-security or malware scan. None of the
validation commands publish artifacts.

Both artifacts publish exact project links for the homepage, source repository,
issue tracker, and changelog. Those four labels and destinations are validated
as package metadata rather than inferred from the checkout.

## Security and resource limits

Manifest and document parsing is not sandboxed or isolated. There are no
enforced input-byte, PDF-page, archive-member, row, cell, chunk, memory,
CPU-time, or parser wall-clock limits. PDF inputs are parsed twice; workbook
loading is not read-only; extracted text and many derived structures are held
in memory. Large, malformed, compressed, or adversarial inputs can consume
substantial resources or exercise vulnerabilities in parser dependencies.

WCL is not a malware scanner, sanitizer, safe document viewer, schema validator,
or substitute for human review. Bounded parsing, stricter schemas,
transactional report publication, OCR, and broader extraction are possible
future directions, not current guarantees. See `SECURITY.md` for reporting and
operational guidance.
