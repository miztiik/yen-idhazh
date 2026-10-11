"""Resolve installed compatible versions to official Linux wheel hashes without installing them."""

import argparse
import hashlib
import json
from email.parser import BytesParser
from html.parser import HTMLParser
from importlib.metadata import version
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import urlopen

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from idhazh.contracts.story_runner import RunnerFile, RunnerRuntimeLock
from idhazh.story_dataset.storage import write_model


class WheelLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.urls.extend(value for key, value in attrs if key == "href" and value)


def resolve_lock(output: Path) -> RunnerRuntimeLock:
    platforms = ["manylinux_2_28_x86_64", "manylinux2014_x86_64", "manylinux_2_17_x86_64"]
    tags = set(cpython_tags((3, 14), abis=["cp314"], platforms=platforms))
    tags.update(compatible_tags((3, 14), interpreter="cp314", platforms=platforms))
    environment = {key: str(value) for key, value in default_environment().items()}
    environment.update(
        python_version="3.14",
        python_full_version="3.14.2",
        sys_platform="linux",
        os_name="posix",
        platform_system="Linux",
        platform_machine="x86_64",
    )
    pending = [
        Requirement(r)
        for r in (
            "torch==2.14.1+cpu",
            "torchvision==0.29.1+cpu",
            "sentence-transformers[image]==6.1.0",
            "transformers==5.19.0",
            "Pillow==12.3.0",
            "pydantic==2.13.5",
            "numpy==2.5.3",
            "scipy==1.18.1",
            "scikit-learn==1.9.1",
        )
    ]
    versions: dict[str, str] = {}
    wheels: dict[str, RunnerFile] = {}
    urls: dict[str, str] = {}
    metadata_hashes: dict[str, str] = {}
    visited: set[tuple[str, tuple[str, ...]]] = set()
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        installed = version(name)
        if Version(installed) not in requirement.specifier:
            raise ValueError(f"installed {name}=={installed} cannot satisfy {requirement}")
        key = (name, tuple(sorted(requirement.extras)))
        if key in visited:
            continue
        visited.add(key)
        if name in ("torch", "torchvision"):
            url = f"https://download.pytorch.org/whl/cpu/{name}/"
            with urlopen(url, timeout=60) as response:
                raw = response.read()
            links = WheelLinks()
            links.feed(raw.decode())
            matches = []
            for link in links.urls:
                absolute = urljoin(url, link)
                filename = unquote(urlsplit(absolute).path.rsplit("/", 1)[-1])
                if not filename.endswith(".whl"):
                    continue
                _, wheel_version, _, wheel_tags = parse_wheel_filename(filename)
                if wheel_version == Version(installed) and tags & wheel_tags:
                    checksum = urlsplit(absolute).fragment.removeprefix("sha256=")
                    matches.append((filename, absolute.split("#", 1)[0], checksum))
            if len(matches) != 1:
                raise ValueError(
                    f"expected one official CPU Linux wheel for {name}, got {len(matches)}"
                )
            filename, download, checksum = matches[0]
            download = download.replace("download-r2.pytorch.org", "download.pytorch.org")
            with urlopen(download + ".metadata", timeout=60) as response:
                raw = response.read()
            metadata_message = BytesParser().parsebytes(raw)
            if metadata_message["Version"] != installed:
                raise ValueError("official CPU wheel version differs")
            dependencies = metadata_message.get_all("Requires-Dist") or []
            size = 0
        else:
            url = f"https://pypi.org/pypi/{name}/{installed}/json"
            with urlopen(url, timeout=60) as response:
                raw = response.read()
            metadata = json.loads(raw)
            eligible = [
                row
                for row in metadata["urls"]
                if row["filename"].endswith(".whl")
                and tags & parse_wheel_filename(row["filename"])[3]
            ]
            if len(eligible) != 1:
                raise ValueError(
                    f"expected one official Linux wheel for {name}, got {len(eligible)}"
                )
            row = eligible[0]
            filename, download, checksum = row["filename"], row["url"], row["digests"]["sha256"]
            size = row["size"]
            dependencies = metadata["info"]["requires_dist"] or []
        versions[name] = installed
        wheels[name] = RunnerFile(path=filename.replace("+", "-"), sha256=checksum, bytes=size)
        urls[name] = download
        metadata_hashes[name] = hashlib.sha256(raw).hexdigest()
        for declaration in dependencies:
            dependency = Requirement(declaration)
            extras = {"", *requirement.extras}
            if dependency.marker is None or any(
                dependency.marker.evaluate({**environment, "extra": extra}) for extra in extras
            ):
                pending.append(dependency)
    lock = RunnerRuntimeLock(
        versions=versions, wheels=wheels, urls=urls, metadata_sha256=metadata_hashes
    )
    write_model(output.with_suffix(".json"), lock)
    lines = [
        f"{name} @ {urls[name]} --hash=sha256:{wheels[name].sha256}" for name in sorted(versions)
    ]
    output.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return lock


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(f"locked {len(resolve_lock(args.output).versions)} compatible Linux distributions")


if __name__ == "__main__":
    main()
