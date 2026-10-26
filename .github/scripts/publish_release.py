"""Publish the checked-out manifest version after successful main validation."""

import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request


def github_api(method, path, payload=None):
    """Treat only GET 404 as absent; fail on authorization/network errors."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "Freshpoint-release",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return None
        raise


def publish(root=Path("."), api=github_api):
    """Create an immutable stable release; never move existing version tags."""
    if os.environ["GITHUB_REF"] != "refs/heads/main":
        raise ValueError("Releases must originate from main")
    version = json.loads(
        (root / "custom_components/freshpoint/manifest.json").read_text()
    )["version"]
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Expected a stable major.minor.patch manifest version")
    tag = f"v{version}"
    release = api("GET", f"releases/tags/{tag}")
    if release is not None:
        if release.get("draft") or release.get("prerelease"):
            raise ValueError(f"{tag} already exists as a draft or prerelease; review manually")
        print(f"{tag} already published; nothing to do")
        return
    notes = (root / f"release_notes/{version}.md").read_text().strip()
    if not notes:
        raise ValueError(f"Release notes for {version} are empty")
    sha = os.environ["GITHUB_SHA"]
    ref = api("GET", f"git/ref/tags/{tag}")
    if ref is not None:
        obj = ref["object"]
        for _ in range(10):
            if obj["type"] == "commit":
                break
            if obj["type"] != "tag":
                raise ValueError(f"Unexpected tag object for {tag}")
            obj = api("GET", f"git/tags/{obj['sha']}")["object"]
        if obj["type"] != "commit" or obj["sha"] != sha:
            raise ValueError(f"Existing tag {tag} points to a different commit; refusing to move it")
    result = api("POST", "releases", {
        "tag_name": tag,
        "target_commitish": sha,
        "name": tag,
        "body": notes,
        "draft": False,
        "prerelease": False,
        "make_latest": "legacy",
    })
    print(f"Published {result['html_url']}")


if __name__ == "__main__":
    publish()
