"""Daily EIA and company-release evidence capture, runnable locally or on Cloud Run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
import urllib.request
import uuid
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from lxml import etree, html

from .prospective import capture_market, checkpoint, now, save, sha


IR_HOST = "ir.corporate.murphyusa.com"
IR_FEED = f"https://{IR_HOST}/rss/pressrelease.aspx"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "musa-pit-evidence-capture/1.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
            if not body.strip():
                raise ValueError(f"empty source response: {url}")
            return body
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"source capture failed after three attempts: {url}") from last_error


def capture_disclosures(root: Path, fetcher=fetch) -> Path:
    """Archive RSS and linked official releases; numeric classification remains a review step."""
    directory = root / "disclosures"
    directory.mkdir(parents=True, exist_ok=False)
    raw_feed = fetcher(IR_FEED)
    (directory / "feed.xml").write_bytes(raw_feed)
    captured = now()
    feed = etree.fromstring(raw_feed, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    items = feed.findall("./channel/item")
    if not items:
        raise ValueError("RSS contains no releases; source coverage cannot be established")
    sources = []
    for item in items:
        url = (item.findtext("link") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != IR_HOST:
            raise ValueError("RSS release URL is outside the official issuer domain")
        raw = fetcher(url)
        source_id = hashlib.sha256(url.encode()).hexdigest()
        filename = f"{source_id}.html"
        (directory / filename).write_bytes(raw)
        text = " ".join(html.fromstring(raw).itertext())
        if "margin" not in text.lower() and "murphy" not in text.lower():
            raise ValueError(f"release content could not be verified: {url}")
        published = item.findtext("pubDate")
        sources.append({
            "title": item.findtext("title"), "url": url, "raw_file": filename,
            "raw_sha256": sha(directory / filename),
            "published_at": parsedate_to_datetime(published).isoformat() if published else None,
            "available_at": now(), "captured_at": now(),
            "availability_method": "FIRST_CAPTURE_CONSERVATIVE",
            "classification_status": "PENDING_DISCLOSURE_REVIEW",
        })
    manifest_path = save(directory / "manifest.json", {
        "source_scope": "ISSUER_RSS_LINKED_RELEASES_ONLY",
        "feed_url": IR_FEED, "feed_sha256": sha(directory / "feed.xml"),
        "feed_captured_at": captured, "sources": sources,
        "audit_status": "CAPTURED_PENDING_REVIEW",
        "negative_disclosure_conclusion_authorized": False,
    })
    # Candidates require human period/target review; this never assimilates
    # reported prior-quarter actuals as current-quarter QTD disclosures.
    from .evidence_intake import queue_disclosures
    queue_disclosures(manifest_path, directory / "review_queue.json")
    return manifest_path


def run_local(root: Path, *, weights: Path, actuals: Path, revision: str,
              include_daily_prices: bool = False) -> Path:
    """Retain partial evidence on failure; return a completed manifest only if all captures work."""
    root.mkdir(parents=True, exist_ok=False)
    status = {"started_at": now(), "code_revision": revision,
              "status": "RUNNING", "errors": [], "evaluation_role": "PROSPECTIVE_CAPTURE"}
    market_manifest = None
    actions = [
        ("market", lambda: capture_market(root, date(2019, 1, 1))),
        ("disclosures", lambda: capture_disclosures(root)),
    ]
    if include_daily_prices:
        from .daily_prices import capture
        def capture_daily():
            capture(root / 'daily_prices')
            return root / 'daily_prices' / 'manifest.json'
        actions.append(('daily_prices', capture_daily))
    for name, action in actions:
        try:
            path = action()
            status[f"{name}_manifest"] = str(path.relative_to(root))
            if name == "market":
                market_manifest = path
        except Exception as exc:
            status["errors"].append({"stage": name, "error": str(exc)})
    if market_manifest:
        current = datetime.now(timezone.utc).date()
        quarter_number = (current.month - 1) // 3 + 1
        begin = date(current.year, (quarter_number - 1) * 3 + 1, 1)
        end = date(current.year + 1, 1, 1) if quarter_number == 4 else date(current.year, quarter_number * 3 + 1, 1)
        from datetime import timedelta
        try:
            path = checkpoint(root, market_manifest, weights, actuals,
                              f"{current.year}Q{quarter_number}", begin, end - timedelta(days=1))
            status["checkpoint"] = str(path.relative_to(root))
        except Exception as exc:
            status["errors"].append({"stage": "checkpoint", "error": str(exc)})
    status["completed_at"] = now()
    status["status"] = "FAILED" if status["errors"] else "COMPLETE"
    status["files"] = {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}
    return save(root / "run.json", status)


def upload_tree(root: Path, bucket, prefix: str) -> None:
    """Create cloud objects exclusively; publish run.json last as the completion marker."""
    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "run.json")
    if (root / "run.json").exists():
        paths.append(root / "run.json")
    for path in paths:
        blob = bucket.blob(f"{prefix}/{path.relative_to(root).as_posix()}")
        blob.metadata = {"sha256": sha(path)}
        blob.upload_from_filename(str(path), if_generation_match=0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive daily MUSA/EIA PIT evidence")
    parser.add_argument("--bucket", default=os.environ.get("ARCHIVE_BUCKET"))
    parser.add_argument("--local-root", type=Path)
    parser.add_argument("--weights", type=Path, default=Path("data/weights.csv"))
    parser.add_argument("--actuals", type=Path, default=Path("data/actuals.csv"))
    parser.add_argument("--daily-prices", action="store_true",
                        default=os.environ.get("MUSA_CAPTURE_DAILY_PRICES") == "1",
                        help="also archive daily EIA wholesale; AAA automation stays disabled")
    args = parser.parse_args(argv)
    if not args.bucket and not args.local_root:
        parser.error("provide --bucket or --local-root")
    revision = os.environ.get("CODE_REVISION", "LOCAL_UNVERSIONED")
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ") + "_" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="musa-daily-") as temp:
        root = args.local_root / run_id if args.local_root else Path(temp) / run_id
        run_path = run_local(root, weights=args.weights, actuals=args.actuals, revision=revision,
                             include_daily_prices=args.daily_prices)
        result = json.loads(run_path.read_text())
        if args.bucket:
            from google.cloud import storage
            upload_tree(root, storage.Client().bucket(args.bucket), f"prospective/daily/{run_id}")
        print(json.dumps({"run_id": run_id, "status": result["status"], "errors": result["errors"]}))
        return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
