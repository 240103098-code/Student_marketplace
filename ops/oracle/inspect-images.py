"""Verify Docker Hub index digests and native linux/arm64 support without pulling."""
import hashlib
import json
import re
import sys
import urllib.request

ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def inspect(image):
    match = re.fullmatch(r"([a-z]+):([a-zA-Z0-9._-]+)(?:@(sha256:[a-f0-9]{64}))?", image)
    if not match:
        raise ValueError("Only official Docker Hub library images accepted")
    name, tag, digest = match.groups()
    with urllib.request.urlopen(
        f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/{name}:pull", timeout=30
    ) as response:
        token = json.load(response)["token"]
    request = urllib.request.Request(
        f"https://registry-1.docker.io/v2/library/{name}/manifests/{digest or tag}",
        headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
        actual = "sha256:" + hashlib.sha256(data).hexdigest()
        if response.headers["Docker-Content-Digest"] != actual:
            raise ValueError("Registry digest mismatch")
    if digest and digest != actual:
        raise ValueError("Requested digest mismatch")
    index = json.loads(data)
    arm = [item["digest"] for item in index.get("manifests", [])
           if item.get("platform", {}).get("os") == "linux"
           and item.get("platform", {}).get("architecture") == "arm64"]
    if not arm:
        raise ValueError("No native linux/arm64 manifest in pinned index")
    return {"image": f"{name}:{tag}@{actual}", "platform": "linux/arm64", "arm_manifests": arm}


if __name__ == "__main__":
    print(json.dumps([inspect(image) for image in sys.argv[1:]], indent=2))
