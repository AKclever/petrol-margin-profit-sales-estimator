from __future__ import annotations

import csv
import io
import json
from datetime import date

import pytest

from musa_nowcast.eia import DownloadError, RegionSeries, download_market, fetch_series


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def test_fetch_series_normalizes_week_and_units():
    payload = {"response": {"data": [
        {"period": "2026-07-10", "value": 2.25},
        {"period": "2026-07-13", "value": "3.10"},
    ]}}

    def opener(request, timeout):
        assert "api_key=secret" in request.full_url
        assert timeout == 30
        return Response(json.dumps(payload).encode())

    assert fetch_series("TEST.W", "secret", date(2026, 7, 1), date(2026, 7, 31), opener) == [
        (date(2026, 7, 6), 225.0), (date(2026, 7, 13), 310.0)
    ]


def test_download_market_aligns_common_weeks_and_writes_provenance(tmp_path):
    observations = {
        "retail": [(date(2026, 7, 6), 310), (date(2026, 7, 13), 305)],
        "spot": [(date(2026, 7, 6), 220)],
    }

    def fetcher(series_id, api_key, start, end):
        assert api_key == "key"
        return observations[series_id]

    output, provenance = tmp_path / "market.csv", tmp_path / "market.json"
    count = download_market(output, provenance, "key", date(2026, 7, 1), date(2026, 7, 31),
                            (RegionSeries("Gulf Coast", "retail", "spot"),), fetcher)
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    metadata = json.loads(provenance.read_text(encoding="utf-8"))
    assert count == 1
    assert rows == [{"week": "2026-07-06", "region": "Gulf Coast",
                     "retail_cpg": "310.0000", "wholesale_cpg": "220.0000"}]
    assert metadata["series"][0]["matched_weeks"] == 1


def test_fetch_series_rejects_missing_data():
    def opener(request, timeout):
        return Response(json.dumps({"response": {}}).encode())

    with pytest.raises(DownloadError, match="no data array"):
        fetch_series("TEST.W", "key", date(2026, 1, 1), date(2026, 2, 1), opener)
