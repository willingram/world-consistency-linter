# Security policy

## Supported versions

Until versioned releases are published, security fixes are made on the latest
maintained code on `main`. If versioned releases are published, fixes will
target the latest released minor version.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the repository owner. Do
not put private documents, personal data, credentials, exploit details, or
generated reports containing sensitive evidence in a public issue. Include the
tool version, platform, command, and the smallest fictional manifest and
document bundle that reproduce the problem where possible.

No response-time or remediation-time service level is promised.

## Threat model

WCL crosses local trust boundaries when it loads a YAML manifest, resolves the
filesystem paths that manifest names, parses document containers and text, and
writes evidence-bearing reports to a caller-selected directory.

- Relative inputs resolve from the manifest directory, but absolute and
  parent-traversing paths are accepted. Symlinks and ordinary filesystem
  resolution are not confined to a bundle root. A manifest can therefore
  direct WCL to any file readable by the running account.
- PDF, DOCX, PPTX, XLSX/XLSM, delimited, YAML/JSON-as-text, and other text
  inputs reach WCL or third-party parsers. OOXML files are ZIP-based containers;
  PDFs and archives can contain complex, compressed, malformed, embedded, or
  externally linked structures. Parser-library vulnerabilities remain
  possible.
- WCL does not deliberately execute formulas or macros, invoke embedded
  objects, fetch external resources, start subprocesses, or make network
  requests during an audit. It does not sanitize active content or external
  links for later opening in another application.
- Parsing is not isolated and has no enforced byte, page, archive-member, row,
  cell, memory, CPU-time, or wall-clock bounds. Large or adversarial inputs can
  exhaust local resources. PDF files are processed by two parsers, and
  workbooks are loaded in non-read-only mode.
- The caller selects the output directory. WCL creates it if necessary and
  sequentially replaces three fixed report files without a transaction.
  Report-writing failures can leave a partial set.
- Reports contain evidence excerpts and may expose document text, metadata,
  personal information, filenames, manifest declarations, and resolved local
  paths. Review reports before sharing them, and treat rendered Markdown as
  untrusted document-derived content.

WCL is not a sandbox, malware scanner, content sanitizer, safe file viewer, or
security boundary. Treat untrusted manifests, source documents, and generated
reports accordingly; keep parser dependencies current and run the tool with
only the filesystem permissions it needs.
