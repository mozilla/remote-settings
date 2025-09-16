# Remote Settings Over Git

## Getting Started

Clone a Remote Settings data repository into a folder:

```bash
git clone https://github.com/mozilla/remote-settings-data.git /mnt/git/remote-settings-data
```

If the container is configured to serve attachments (see `SELF_CONTAINED` below), make sure to install Git LFS and pull the LFS files:

```bash
git lfs install
git lfs pull
git lfs fsck
```

Build the container:

```bash
docker build -t remote-settings-git-reader .
```

Then you can start the application with:

```bash
docker run --rm -p 8000:8000 \
    -e GIT_REPO_PATH=/mnt/data \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data \
    remote-settings-git-reader
```

## Settings

- ``GIT_REPO_PATH``: the path to the Git repository to use.
- ``SELF_CONTAINED`` (default: `false`): if set to `true`, the application will serve all necessary content from the Git repository, including
  attachments and certificates chains.
- ``ATTACHMENTS_BASE_URL`` (default: `None`): this URL will be used as the base URL for attachments. If `SELF_CONTAINED` is `false`, this URL is mandatory, otherwise the current domain will be used by default (`Host` request header).
