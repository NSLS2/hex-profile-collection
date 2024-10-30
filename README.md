# NSLS-II-HEX Bluesky Profile

## Conda environment

Requires `2024-2.3-py311-tiled` conda environment, with overlays w/ non-tagged source installs of ophyd-async, bluesky, hextools, 

### Update on 5/15/24:

We are switching to the latest conda environment deployed for the 2024 Cycle 2 - `2024-2.0-py310-tiled`.
The environment does not provide the latest bluesky code with the `TiledWriter` callback, unreleased to date.
We installed the latest bluesky into overlays with the following command:

```bash
$ pip install --prefix=/nsls2/data/hex/shared/config/bluesky_overlays/2024-2.0-py310-tiled -I --no-deps --no-build-isolation git+https://github.com/bluesky/bluesky.git@mainCollecting git+https://github.com/bluesky/bluesky.git@main
  Cloning https://github.com/bluesky/bluesky.git (to revision main) to /tmp/pip-req-build-2kav0g4e
  Running command git clone --filter=blob:none --quiet https://github.com/bluesky/bluesky.git /tmp/pip-req-build-2kav0g4e
  Resolved https://github.com/bluesky/bluesky.git to commit bc8222be2e099a00baafcede1d761d61b213bf19
  Preparing metadata (pyproject.toml) ... done
Building wheels for collected packages: bluesky
  Building wheel for bluesky (pyproject.toml) ... done
  Created wheel for bluesky: filename=bluesky-1.13.0a4.dev175+gbc8222be-py3-none-any.whl size=310491 sha256=5ca5f93a2471e4d9ebac3d521789ae87c5aed033168a1c7933c726f7cafd2673
  Stored in directory: /tmp/pip-ephem-wheel-cache-afvgkk8r/wheels/41/2d/04/e7440b17766879028a7fb6632b555f48338c394596dda55995
Successfully built bluesky
Installing collected packages: bluesky
Successfully installed bluesky-1.13.0a4.dev175+gbc8222be
```

```bash
$ pip install --prefix=/nsls2/data/hex/shared/config/bluesky_overlays/2024-2.0-py310-tiled -I --no-deps --no-build-isolation ophyd-async --pre
Collecting ophyd-async
  Downloading ophyd_async-0.3a4-py3-none-any.whl.metadata (6.3 kB)
Downloading ophyd_async-0.3a4-py3-none-any.whl (90 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 90.7/90.7 kB 1.5 MB/s eta 0:00:00
Installing collected packages: ophyd-async
Successfully installed ophyd-async-0.3a4
```

To use it with `bsui`:
```bash
BS_PYTHONPATH=/nsls2/data/hex/shared/config/bluesky_overlays/2024-2.0-py310-tiled BS_ENV=2024-2.0-py310-tiled bsui
```


### Source-installed repositories

- `ophyd-async`: https://github.com/NSLS-II-TST/ophyd-async/tree/add-vimba-support (based on the https://github.com/bluesky/ophyd-async/pull/154 PR branch)
- `bluesky`: https://github.com/genematx/bluesky/tree/add-tiled-writer and https://github.com/bluesky/bluesky/pull/1660 - merged, see the overlays configuration above
- `tiled`: https://github.com/danielballan/tiled/tree/register-hdf5-internal (merged https://github.com/bluesky/tiled/pull/687) - released via tiled v0.1.0a117/a118, already in the 2024-2.0-py310-tiled.


## Tiled configuration

OUTDATED:

~~Runs locally on `xf27id1-ws2` machine. Check it with:~~

```bash
$ systemctl status tiled
```

New configuration: TBD


## Prefect configuration

- https://github.com/NSLS-II-HEX/workflows/tree/export-nxs and https://github.com/NSLS-II-HEX/workflows/pull/4
~~- conda environment: `/nsls2/users/workflow-hex/conda_envs/dev`~~
- conda environment: `...`


## PandA IOC

- The IOC runs on `xf27id1-ioc1` (Panda 1)
- Source from https://github.com/PandABlocks/PandABlocks-ioc/pull/102 (https://github.com/jwlodek/PandABlocks-ioc/tree/add-create-dir-depth) - WIP


## PandA configuration

http://xf27id1-panda1.nsls2.bnl.local:8008/gui/PANDA/layout/

![PandA config for HEX tomo](img/panda.png)
