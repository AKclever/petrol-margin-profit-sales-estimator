import json

import pytest

from musa_nowcast import daily_capture as d


def test_release_capture_preserves_source_and_requires_review(tmp_path):
    url = f"https://{d.IR_HOST}/release"
    rss = f'''<rss><channel><item><title>Update</title><link>{url}</link>
      <pubDate>Wed, 07 Oct 2026 12:00:00 +0000</pubDate></item></channel></rss>'''.encode()
    raw = b"<html><body>Murphy USA retail margin update</body></html>"
    result = json.loads(d.capture_disclosures(tmp_path, lambda u: rss if u == d.IR_FEED else raw).read_text())
    evidence = result["sources"][0]
    assert evidence["classification_status"] == "PENDING_DISCLOSURE_REVIEW"
    assert (tmp_path / "disclosures" / evidence["raw_file"]).read_bytes() == raw
    assert result["negative_disclosure_conclusion_authorized"] is False
    assert evidence["available_at"] != evidence["published_at"]


def test_empty_feed_does_not_become_a_negative_disclosure_conclusion(tmp_path):
    with pytest.raises(ValueError, match="coverage"):
        d.capture_disclosures(tmp_path, lambda u: b"<rss><channel/></rss>")
    assert not (tmp_path / "disclosures" / "manifest.json").exists()


def test_partial_failures_are_preserved_and_run_is_failed(tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("source unavailable")
    monkeypatch.setattr(d, "capture_market", fail)
    monkeypatch.setattr(d, "capture_disclosures", fail)
    result = json.loads(d.run_local(tmp_path / "run", weights=tmp_path / "weights",
                                   actuals=tmp_path / "actuals", revision="test").read_text())
    assert result["status"] == "FAILED"
    assert {error["stage"] for error in result["errors"]} == {"market", "disclosures"}


def test_cloud_upload_never_overwrites_and_publishes_marker_last(tmp_path):
    (tmp_path / "raw").write_text("evidence")
    (tmp_path / "run.json").write_text("{}")
    calls = []
    class Blob:
        def __init__(self, name):
            self.name = name
        def upload_from_filename(self, path, **kwargs):
            calls.append((self.name, kwargs))
    class Bucket:
        def blob(self, name):
            return Blob(name)
    d.upload_tree(tmp_path, Bucket(), "unique-run")
    assert calls[-1][0] == "unique-run/run.json"
    assert all(kwargs["if_generation_match"] == 0 for _, kwargs in calls)


def test_optional_daily_stage_failure_is_reported(tmp_path,monkeypatch):
    from musa_nowcast import daily_prices
    def fail(*args,**kwargs):
        raise RuntimeError('test source unavailable')
    monkeypatch.setattr(d,'capture_market',fail)
    monkeypatch.setattr(d,'capture_disclosures',fail)
    monkeypatch.setattr(daily_prices,'capture',fail)
    result=json.loads(d.run_local(tmp_path/'run',weights=tmp_path/'w',actuals=tmp_path/'a',
        revision='test',include_daily_prices=True).read_text())
    assert {e['stage'] for e in result['errors']}=={'market','disclosures','daily_prices'}
    assert result['status']=='FAILED'
