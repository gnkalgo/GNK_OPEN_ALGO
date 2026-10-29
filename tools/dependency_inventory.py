"""Generate a review inventory from locked packages, without downloading reference code.

This records license declarations; it is not a legal approval or vulnerability scan.
Run with backend's installed, pinned Python environment after npm ci.
"""

import argparse
import hashlib
import json
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "DEPENDENCY-INVENTORY.json"
LOCKS = [ROOT / "frontend/package-lock.json", ROOT / "backend/requirements.lock"]


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify inventory covers current lockfiles"
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Block release until required review areas have evidence",
    )
    args = parser.parse_args()
    hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in LOCKS}
    if args.check or args.release:
        inventory = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if inventory["lockfile_sha256"] != hashes:
            sys.exit(
                "Dependency inventory is stale. Regenerate and review the changed packages."
            )
        if args.release:
            approvals = json.loads((ROOT / "docs/RELEASE-APPROVAL.json").read_text())
            if approvals.get("lockfile_sha256") != hashes:
                sys.exit("Release blocked: approval does not cover current lockfiles.")
            required = {
                "owner_license",
                "source_provenance",
                "dependency_licenses_and_notices",
                "broker_and_market_data_terms",
                "regulatory_scope",
                "security_and_recovery",
            }
            reviews = approvals.get("reviews", {})
            pending = sorted(
                key
                for key in required
                if reviews.get(key, {}).get("status") != "approved"
                or not reviews.get(key, {}).get("reviewer")
                or not reviews.get(key, {}).get("evidence")
            )
            if pending:
                sys.exit("Release blocked: " + ", ".join(pending))
        print(
            "Release review record is complete; validate the named evidence before deployment."
            if args.release
            else "Dependency inventory matches both lockfiles; this is not legal approval."
        )
        return
    packages = []
    for location, package in json.loads(LOCKS[0].read_text())["packages"].items():
        if not location:
            continue
        packages.append(
            {
                "ecosystem": "npm",
                "name": location.rsplit("node_modules/", 1)[-1],
                "version": package["version"],
                "license_declaration": package.get("license", "UNKNOWN"),
                "scope": "development" if package.get("dev") else "runtime",
                "integrity": package.get("integrity"),
                "review": "pending",
            }
        )
    for line in LOCKS[1].read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        declaration = "UNKNOWN"
        matched = False
        try:
            dist = metadata.distribution(name)
            matched = dist.version == version
            if matched:
                declaration = (
                    dist.metadata.get("License-Expression")
                    or dist.metadata.get("License")
                    or "UNKNOWN"
                )
                if declaration == "UNKNOWN":
                    declaration = (
                        "; ".join(
                            c
                            for c in dist.metadata.get_all("Classifier", [])
                            if c.startswith("License ::")
                        )
                        or "UNKNOWN"
                    )
        except metadata.PackageNotFoundError:
            pass
        packages.append(
            {
                "ecosystem": "pypi",
                "name": name,
                "version": version,
                "license_declaration": declaration,
                "metadata_matches_lock": matched,
                "scope": "backend-and-tooling",
                "review": "pending",
            }
        )
    inventory = {
        "schema_version": 1,
        "status": "declarations-only-not-legal-clearance",
        "lockfile_sha256": hashes,
        "components": sorted(
            packages, key=lambda p: (p["ecosystem"], p["name"], p["version"])
        ),
    }
    OUTPUT.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    unknown = sum(p["license_declaration"] == "UNKNOWN" for p in packages)
    print(
        f"Recorded {len(packages)} locked components; {unknown} missing license declarations; all require release review."
    )


if __name__ == "__main__":
    main()
