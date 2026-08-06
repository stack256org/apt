# keys

The **public** half of the repository signing key lives here, as
`stack256-archive-keyring.asc`, once it has been generated (see step 3 of the
root README).

It is committed so the published index and the key that signed it can be
checked against each other, and so there is a second place to fetch it from
besides the Pages site.

The private half belongs in this repository's `APT_SIGNING_KEY` secret and
nowhere else — never in this directory, and never in a commit.
