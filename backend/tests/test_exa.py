"""Tests for the Exa search client."""

from __future__ import annotations

import pytest


class TestExaClient:
    """Integration tests for the Exa search client."""

    def test_search_returns_results(self, client):
        """Exa search returns structured results with title, url, text."""
        resp = client.post(
            "/exa/search",
            json={
                "query": "best wireless mouse under 30",
                "num_results": 5,
            },
        )
        # Without EXA_API_KEY, falls back to mock data
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        if data["results"]:
            r = data["results"][0]
            assert "title" in r
            assert "url" in r
            assert "text" in r

    def test_search_respects_num_results(self, client):
        """num_results parameter limits response count."""
        resp = client.post(
            "/exa/search",
            json={
                "query": "test",
                "num_results": 3,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 3

    def test_search_empty_query_rejected(self, client):
        """Empty query returns 422."""
        resp = client.post("/exa/search", json={"query": ""})
        assert resp.status_code == 422

    def test_mock_mode_returns_sample_data(self, client):
        """When EXA_API_KEY is absent, mock data is returned — always runs."""
        resp = client.post(
            "/exa/search",
            json={
                "query": "wireless mouse",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0
        assert "results" in data
