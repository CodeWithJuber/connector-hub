"""Live read-only tests. These do not use recorded fixtures.

Data source: https://api.github.com/meta (GitHub REST API, retrieved live).
"""

import json
import urllib.request

import pytest


@pytest.mark.integration
def test_github_public_metadata_is_live_and_structured() -> None:
    request = urllib.request.Request(
        "https://api.github.com/meta",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "omni-connector-hub-ci"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        data = json.load(response)
    assert response.status == 200
    assert isinstance(data, dict)
    assert isinstance(data.get("hooks"), list)


@pytest.mark.integration
@pytest.mark.credentialed
def test_hetzner_locations_with_protected_credential() -> None:
    import os

    token = os.getenv("HETZNER_API_TOKEN")
    if not token:
        pytest.skip(
            "HETZNER_API_TOKEN is absent; create a read-only token in Hetzner Cloud Console"
        )
    request = urllib.request.Request(
        "https://api.hetzner.cloud/v1/locations",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "omni-connector-hub-ci"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        data = json.load(response)
    assert response.status == 200
    assert isinstance(data.get("locations"), list)
