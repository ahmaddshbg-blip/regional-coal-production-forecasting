# Raw Data Manifest

This directory holds immutable local source snapshots and is ignored by Git.
Do not edit the extracted text files in place.

## Expected files

| File | Source archive | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `MinesProdQuarterly.txt` | `MinesProdQuarterly.zip` | 261,773,843 | `1B3A84245EA17A267BA34B642F0A3513FCEAEAF764D95774ED1D318612817B12` |
| `Mines.txt` | `Mines.zip` | 39,363,960 | `38776A237EB6B99A39A1F64C0CA5B8E42B5C320ACE3FCDDB2E6C6C2F508A22F4` |

Acquired manually from the
[MSHA Open Government Data portal](https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp)
on 2026-09-20.

Both files are pipe-delimited text with a header row. Read them using an
explicit encoding; the initial audit used `latin-1` because some free-text
fields contain legacy byte values.

If a later download has a different hash, treat it as a new source snapshot.
Do not overwrite this snapshot without recording the acquisition date, new
hashes, and affected downstream artifacts.
