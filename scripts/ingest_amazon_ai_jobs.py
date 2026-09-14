from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import urllib.parse
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SEARCH_URL = "https://www.amazon.jobs/en/search.json"
SELECTED_JOB_IDS = (
    "10451070",  # AI Agent Engineer, Beijing
    "10504493",  # Applied Scientist, Shanghai
    "10489936",  # Applied Scientist, Beijing
    "10528110",  # Data Scientist, Shanghai
    "10504610",  # Senior Data Scientist, Shanghai
    "10501867",  # Senior Data Scientist, Shanghai
    "10501752",  # Technical AI Product Manager, Shanghai
    "10465398",  # Technical AI Product Manager, Shanghai
    "10490159",  # Early-career Solutions Architect, Shanghai
    "10496564",  # Early-career Software Development Engineer, Shanghai
)
COMPANY_TERMS = re.compile(
    r"(?:Amazon(?:\.com|ian(?:s)?)?|AWS|Alexa|Audible|Kindle|Prime Video)",
    flags=re.IGNORECASE,
)
URL = re.compile(r"https?://\S+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "li", "p"}:
            self.parts.append("\n")

    def text(self) -> str:
        value = html.unescape("".join(self.parts))
        lines = (re.sub(r"\s+", " ", line).strip() for line in value.splitlines())
        return "\n".join(line for line in lines if line)


def _plain_text(value: str | None) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    return parser.text()


def _fetch_jobs() -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "base_query": "AI",
            "country": "CHN",
            "offset": 0,
            "result_limit": 100,
        }
    )
    result = subprocess.run(
        ["curl", "-fsSL", f"{SEARCH_URL}?{query}"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    return payload["jobs"]


def _anonymize(value: str | None) -> str:
    without_urls = URL.sub("[SOURCE_URL_REMOVED]", _plain_text(value))
    return COMPANY_TERMS.sub("[COMPANY_A]", without_urls)


def _anonymous_record(job: dict[str, Any], index: int, collected_at: str) -> dict[str, Any]:
    return {
        "case_id": f"china-ai-role-{index:02d}",
        "title": _anonymize(job["title"]),
        "location": job["location"],
        "job_category": job["job_category"],
        "description": _anonymize(job["description"]),
        "basic_qualifications": _anonymize(job["basic_qualifications"]),
        "preferred_qualifications": _anonymize(job["preferred_qualifications"]),
        "posted_date": job["posted_date"],
        "collected_at": collected_at,
        "anonymization": {
            "company": "[COMPANY_A]",
            "removed_fields": ["company_name", "application_url", "team", "internal_uuid"],
        },
    }


def ingest(output_root: Path) -> tuple[Path, Path]:
    jobs_by_id = {job["id_icims"]: job for job in _fetch_jobs()}
    missing_ids = set(SELECTED_JOB_IDS) - jobs_by_id.keys()
    if missing_ids:
        missing = ", ".join(sorted(missing_ids))
        raise RuntimeError(f"Selected jobs are no longer present in the China search: {missing}")

    collected_at = datetime.now(UTC).isoformat()
    selected_jobs = [jobs_by_id[job_id] for job_id in SELECTED_JOB_IDS]
    raw_payload = {
        "source": SEARCH_URL,
        "query": {"base_query": "AI", "country": "CHN"},
        "collected_at": collected_at,
        "jobs": selected_jobs,
    }
    anonymous_payload = [
        _anonymous_record(job, index, collected_at)
        for index, job in enumerate(selected_jobs, start=1)
    ]

    raw_path = output_root / "jd_raw" / "amazon_china_ai.json"
    anonymous_path = output_root / "jd_anonymized" / "china_ai_jobs.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    anonymous_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    anonymous_path.write_text(
        json.dumps(anonymous_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return raw_path, anonymous_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and anonymize selected China AI JDs.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/private"),
        help="Private output root (default: data/private)",
    )
    arguments = parser.parse_args()
    raw_path, anonymous_path = ingest(arguments.output_root)
    print(f"raw: {raw_path}")
    print(f"anonymized: {anonymous_path}")


if __name__ == "__main__":
    main()
