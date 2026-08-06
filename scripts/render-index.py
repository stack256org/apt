#!/usr/bin/env python3
"""Render the landing page's product list from what was actually published.

The page used to carry a hand-written table with one row in it. That is fine
for exactly as long as there is one product, and wrong the first time someone
ships a second and forgets the HTML — which is the same failure that put a
`1` / `1.4` / `1.4.2` tag ladder in Docket's README while 0.1.0 was the only
release that existed.

Two inputs, and the split between them is the point:

  products.json   what a product IS — display name, summary, links. Editorial,
                  and the only place a product is named.
  dists/.../Packages  what is actually DOWNLOADABLE — version and architectures,
                  read from the index this very run generated.

A card is emitted only for a product whose package appears in that index. So
the page cannot advertise something that failed to build, and the version on it
is never a number someone forgot to bump: there is nowhere to type one.

Usage: render-index.py <dist-dir>
"""

import html
import json
import pathlib
import re
import sys

BEGIN = "<!-- BEGIN GENERATED: products -->"
END = "<!-- END GENERATED: products -->"


def parse_packages(dist: pathlib.Path) -> dict[str, dict]:
    """Read every binary-*/Packages into {package: {version, arches}}.

    Architectures accumulate across the per-arch indexes rather than being
    declared anywhere: a product that only managed to build amd64 this run
    should say amd64, not claim both because products.json is optimistic.
    """
    found: dict[str, dict] = {}

    for packages_file in sorted(dist.glob("dists/stable/main/binary-*/Packages")):
        # Stanzas are separated by a blank line; RFC822-ish, and we only need
        # three fields, so a full parser would be more code than it is worth.
        for stanza in packages_file.read_text().split("\n\n"):
            fields = dict(
                re.match(r"([A-Za-z-]+): (.*)", line).groups()
                for line in stanza.splitlines()
                if re.match(r"([A-Za-z-]+): (.*)", line)
            )
            name = fields.get("Package")
            if not name:
                continue

            entry = found.setdefault(name, {"version": fields.get("Version", ""), "arches": set()})
            if fields.get("Architecture"):
                entry["arches"].add(fields["Architecture"])
            # If two arches somehow carry different versions, show the lower one
            # rather than the luckier one — it is the version every documented
            # architecture can actually install.
            if fields.get("Version") and fields["Version"] < entry["version"]:
                entry["version"] = fields["Version"]

    return found


def card(product: dict, published: dict) -> str:
    name = html.escape(product.get("name") or product["package"])
    package = html.escape(product["package"])
    summary = html.escape(product.get("summary", ""))
    version = html.escape(published["version"])
    arches = " · ".join(sorted(published["arches"])) or "—"

    links = []
    if product.get("homepage"):
        links.append(f'<a href="{html.escape(product["homepage"])}">About</a>')
    if product.get("repo"):
        links.append(
            f'<a href="https://github.com/{html.escape(product["repo"])}">Source</a>'
        )

    return f"""          <div class="product">
            <div class="product-head">
              <h3>{name}</h3>
              <span class="version">{version}</span>
            </div>
            <p>{summary}</p>
            <p class="arch">{html.escape(arches)}</p>
            <p class="install"><code>sudo apt install {package}</code></p>
            <p class="links">
              {chr(10).join("              " + link for link in links).strip()}
            </p>
          </div>"""


def main() -> int:
    dist = pathlib.Path(sys.argv[1])
    root = pathlib.Path(__file__).resolve().parent.parent

    products = json.loads((root / "products.json").read_text())["products"]
    published = parse_packages(dist)

    cards = [
        card(p, published[p["package"]])
        for p in products
        if p.get("package") and p["package"] in published
    ]

    if cards:
        body = '        <div class="products">\n' + "\n".join(cards) + "\n        </div>"
    else:
        # Reachable on an `allow_empty` bring-up publish. Saying so plainly beats
        # rendering an empty grid that reads as a broken page.
        body = (
            '        <div class="empty">No packages are published yet. The '
            "repository, its signing key and each product's installer are already "
            "being served — packages appear here as products cut their first "
            "release.</div>"
        )

    page = (root / "index.html").read_text()
    if BEGIN not in page or END not in page:
        print(f"::error file=index.html::missing {BEGIN} / {END} markers", file=sys.stderr)
        return 1

    page = re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END),
        f"{BEGIN}\n{body}\n        {END}",
        page,
        flags=re.S,
    )
    (dist / "index.html").write_text(page)

    listed = ", ".join(f"{p['package']} {published[p['package']]['version']}"
                       for p in products
                       if p.get("package") and p["package"] in published) or "none"
    print(f"landing page: {len(cards)} product card(s) — {listed}")

    # A product listed in products.json whose package never made it into the
    # index is the interesting case: it means a release is missing or a build
    # failed. Silence there would make the page look simply "smaller".
    for p in products:
        if p.get("package") and p["package"] not in published:
            print(
                f"::warning::{p['package']} is in products.json but not in the "
                "published index, so it has no card on the landing page."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
