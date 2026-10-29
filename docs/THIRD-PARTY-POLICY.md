# Third-party, source provenance and release policy

Reviewed 29 October 2026. This is an engineering review record, not a legal opinion or a claim of exclusive ownership of every pre-existing file.

## OpenAlgo reference boundary

The public [OpenAlgo repository](https://github.com/marketcalls/openalgo) was consulted for broad trading-platform concepts: account connections, strategy configuration, orders and operational status. Its [License.md](https://github.com/marketcalls/openalgo/blob/main/License.md) identifies GNU Affero General Public License version 3. No OpenAlgo source, assets, API integrations or runtime URLs were imported in this change. The earlier frontend reference review is retained in [REFERENCE-AUDIT.md](REFERENCE-AUDIT.md); its historical claims are not an independent authorship certification.

General concepts can inform GNK requirements; source text, distinctive assets, documentation text and integrations require separate provenance and licensing analysis. Renaming a copied implementation does not remove its original obligations. If a retained component is found to contain third-party material, preserve its attribution, identify the exact version and license, and either comply with applicable terms or replace it through an independently specified implementation. Do not remove notices to make a codebase appear original.

The scope of this work is not a forensic code-similarity or ownership audit. Existing GNK source and supplied logo ownership must be confirmed by the rights holder before release. No GNK distribution license has been selected automatically; that decision needs the owner's intended business model and rights review.

## Dependency inventory

[DEPENDENCY-INVENTORY.json](DEPENDENCY-INVENTORY.json) enumerates 308 package-lock and requirements.lock entries, including development tools and platform-specific optional packages. It records declared licenses and exact versions, npm integrity where provided, and whether installed Python metadata matches the lock. It is not a complete SBOM of container OS packages, bundled native libraries, fonts or market data, nor an approval of declared licenses.

Generate after installing the pinned backend environment and `npm ci`:

```powershell
.\backend\.venv\Scripts\python.exe tools/dependency_inventory.py
.\backend\.venv\Scripts\python.exe tools/dependency_inventory.py --check
.\backend\.venv\Scripts\python.exe tools/dependency_inventory.py --release
```

`--check` detects lockfile drift; it does not verify license-file content or grant distribution permission. `--release` additionally requires completed reviews and supporting evidence in [RELEASE-APPROVAL.json](RELEASE-APPROVAL.json). This is a local release preflight; it is not yet enforced by the existing deployment script. All reviews currently remain pending. Normal CI verifies lockfile coverage and does not represent a production release approval.

Specific review queue from installed metadata:

- Psycopg and psycopg-binary declare LGPL-3.0-only. Review the actual packaging/linking and bundled library obligations for the shipped container or distribution.
- Certifi and Lightning CSS packages declare MPL-2.0. Review applicable file notices, modifications and distribution scope; build-tool use and distributed runtime artifacts require different analysis.
- Lucide declares ISC; review icon attribution and preserve notices. Package metadata alone does not verify GNK artwork rights.
- Other declarations include MIT, BSD, Apache, PSF, CC-BY, CC0, BlueOak and Unlicense. Retain required notices and review attribution, patent and combined-license terms for the exact artifact.
- Inspect native wheel libraries, base image package licenses, fonts, screenshots, documentation and any future datasets separately. A package version match is not a vulnerability scan or proof of authenticity.

Before adding a dependency: record origin, exact version, license files, use/distribution scope, modifications, notice/source obligations, vulnerability review and decision owner. Reject unknown/unreviewed components at release. Favor a small dependency set, but do not remove a dependency solely because it is copyleft without assessing actual obligations and architecture.

## Regulatory and broker release review

GNK's selected business direction is a multi-user commercial platform with live broker execution. Determine whether GNK is a software vendor, algo provider, research/advisory service or another regulated role for each offering. Do not infer eligibility from a working API login.

The [SEBI timeline circular dated 30 September 2025](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf) specifies full applicability of the retail algo framework from 1 April 2026. The [NSE system-audit circular dated 22 April 2026](https://nsearchives.nseindia.com/content/circulars/INSP73850.pdf) includes controls concerning retail algorithmic API access. These are source references for an applicability review, not an exhaustive or guaranteed-current set of requirements.

Before a live pilot, obtain written determination of the applicable broker/exchange/API onboarding, provider/strategy registration, identification/tagging, hosting, static egress, authentication, permissible orders and audit requirements. Confirm each exchange segment separately and check later circulars. Also review broker commercial API terms, market data storage/redistribution rights, customer consent, privacy, retention, disclosures and incident procedures. Use official broker/exchange contracts, not reference-project adapters or endpoints.

Record named reviewers and evidence for owner license, provenance, dependency notices, broker/data terms, regulatory scope and security/recovery in the release record. Never label the product SEBI-approved, exchange-certified or live-ready without specific verifiable authorization.
