# apt.stack256.org

The signed APT repository for **every** Stack256 product, served from GitHub
Pages at `https://apt.stack256.org`.

```text
deb [signed-by=/usr/share/keyrings/stack256-archive-keyring.gpg] https://apt.stack256.org stable main
```

One source line and one signing key, whatever a customer installs.

## How it works

**No `.deb` files live in this repository.** Each product publishes its
packages to its own GitHub Release; `.github/workflows/reindex.yml` collects the
newest non-prerelease release from every product in [`products.json`](products.json),
generates `Packages` and `Release`, signs `Release`, and deploys the result to
Pages.

```text
product release (paco, …)  ──repository_dispatch──▶  reindex.yml  ──▶  Pages
        │                                                 │
        └── .deb assets ◀────────── gh release download ───┘
```

That split is deliberate. The signing key exists in exactly one repository's
secrets, publishing is serialised in one place, and every product's release
pipeline stays independent of the others. Per-product apt sources would mean N
source lines and N keys for N products, which gets worse with every product.

The index is rebuilt from scratch each time, so it always reflects the current
set of latest releases — nothing accumulates and nothing goes stale.

### Layout it publishes

```text
/index.html                                    landing page
/stack256-archive-keyring.gpg                  public key clients install
/paco-archive-keyring.gpg                      copy, for paco v0.1.0 only
/install.sh                                    a product's installer (see below)
/pool/*.deb                                    collected from product releases
/dists/stable/Release                          generated index
/dists/stable/InRelease                        inline-signed (modern apt)
/dists/stable/Release.gpg                      detached signature (older apt)
/dists/stable/main/binary-amd64/Packages[.gz]
/dists/stable/main/binary-arm64/Packages[.gz]
```

The keyring is named after the **organisation**, not a product, because one key
signs the index for all of them. `paco-archive-keyring.gpg` is a copy kept only
because paco v0.1.0's installer already fetches that path; it can go once no
supported release references it.

## Adding, and removing, a product

`products.json` is the **only** place a product is named. Nothing in the
workflow hardcodes one, so no product's absence can break another's packages:

```json
{
  "products": [
    { "repo": "Stack256org/paco", "installer": "install.sh", "publish_as": "install.sh" },
    { "repo": "Stack256org/docket", "installer": "install.sh", "publish_as": "docket/install.sh" },
    { "repo": "Stack256org/something-else" }
  ]
}
```

- `repo` — where to take the newest non-prerelease release's `.deb` assets from.
- `installer` / `publish_as` — optional. The path in the product's repository,
  and the path it is served at here. Omit both if a product ships no installer.

Two products claiming the same `publish_as` is refused rather than letting one
silently overwrite the other, and a `publish_as` that escapes the site root is
refused too.

**Removing a product is just deleting its entry.** The index and the whole site
are rebuilt from scratch on every run, so its packages and installer disappear
on the next publish with nothing left behind and no other product touched. A
product with no release yet is skipped with a note rather than failing the run,
so this repository stays publishable while a new product is still being set up.

Each product's release workflow notifies this one after publishing its assets:

```yaml
- name: Ask apt.stack256.org to reindex
  env:
    GH_TOKEN: ${{ secrets.APT_DISPATCH_TOKEN }}
  run: gh api repos/Stack256org/apt/dispatches -f event_type=reindex
```

The event type is deliberately generic — this repository serves every product,
so a per-product event name would mean carrying a growing list of names that
all mean the same thing.

## Setup

Done, except where noted:

- [x] Repository public — an APT repository has to be fetchable anonymously.
- [x] Pages enabled with **GitHub Actions** as the source, custom domain
      `apt.stack256.org`, Let's Encrypt certificate issued. The domain comes
      from the `CNAME` file in the published artifact; with Actions as the
      source, a deployment has to exist before the domain can be set at all.
- [x] Signing key generated; private half in the `APT_SIGNING_KEY` secret.
      **Keep an offline backup** — losing it means every client has to install a
      new keyring by hand before it can update again.
- [ ] `APT_DISPATCH_TOKEN`, so a product release reindexes this site
      immediately instead of waiting for the scheduled run. See
      [Reindex triggers](#reindex-triggers) below.

## Reindex triggers

Three, in descending order of how quickly they react:

| Trigger | When | Needs a token |
| --- | --- | --- |
| `repository_dispatch` | a product publishes a release | yes |
| `schedule` | daily, 04:17 UTC | no |
| `workflow_dispatch` | by hand | no |

The schedule is a **backstop, not the main path**. Without it, a missing or
expired `APT_DISPATCH_TOKEN` means a release publishes its `.deb` files and the
site silently keeps serving the previous version — the packages exist, but
`apt install` cannot see them, and nothing anywhere says why. With it, the worst
case is a day's delay instead of indefinite staleness. It costs one rebuild a
day, and rebuilding is idempotent: the index is regenerated from whatever the
current latest releases are.

### `APT_DISPATCH_TOKEN`

A fine-grained PAT with **Contents: write** on *this* repository — write, not
read. `POST /repos/{owner}/{repo}/dispatches` is listed under Contents with
`write` in GitHub's fine-grained permission reference, and a read-only token
fails with a 403 that says nothing about the cause. It needs **no** access to
the product repository: it only asks this one to rebuild.

Set it once at the organisation level rather than per repository, so every
future product inherits it:

```bash
gh secret set APT_DISPATCH_TOKEN --org Stack256org --visibility all
```

Per repository, if you would rather scope it narrowly:

```bash
gh secret set APT_DISPATCH_TOKEN --repo Stack256org/paco
```

## Verifying a publish

The workflow already checks its own output the way a client will — it verifies
`InRelease` against the exported public key in a scratch keyring, and asserts
every `Filename:` in the index exists. To check from outside:

```bash
curl -fsSL https://apt.stack256.org/dists/stable/InRelease | gpg --verify
curl -fsSI https://apt.stack256.org/stack256-archive-keyring.gpg | head -1
```

If `apt update` reports `NO_PUBKEY` or a missing `Release`, the usual cause is
step 3 not having been done — the workflow fails loudly rather than publishing
an unsigned index, so an unsigned repository should never be reachable.
