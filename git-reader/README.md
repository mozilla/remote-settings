# Remote Settings Over Git

## Getting Started

Clone a Remote Settings data repository into a folder:

```bash
git clone git@github.com:leplatrem/remote-settings-data.git /mnt/git/remote-settings-data
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

### Using SSH keys

When cloning the repository anonymously (from `https://...`) the Git LFS is rate-limited and it is very likely that you will hit the limit when pulling the LFS files.

To avoid this, we clone the repository via SSH for authentication.

Since the container is going to regularly run Git fetch commands to keep the repository up to date, you need to let the container use your SSH keys. There are two approaches.

1. Forward the host SSH agent into the container.

This requires to have a SSH agent working on the host. It has the advantage of not requiring the container to have access to the actual key and passphrase (if any).

```bash
docker run --rm -p 8000:8000 \
    -e GIT_REPO_PATH=/mnt/data \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data \
    -e SSH_AUTH_SOCK=/app/ssh-agent \
    -v $SSH_AUTH_SOCK:/app/ssh-agent \
    remote-settings-git-reader
```

2. Or pass the private key file into the container.

This requires to have the private key file accessible on the host. You can mount the directory containing the key file into the container. The SSH key **should not** require any passphrase.

```bash
mkdir ssh-material/
cp ~/.ssh/id_ed25519* ssh-material/
ssh-keyscan github.com >> ssh-material/known_hosts
cat > ssh-material/config <<EOF
Host github.com
  HostName github.com
  User git
  IdentityFile /app/.ssh/id_ed25519
EOF
```

And then mount the SSH material directory into the container:

```bash
docker run --rm -p 8000:8000 \
    -e GIT_REPO_PATH=/mnt/data \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data \
    -v `pwd`/ssh-material:/app/.ssh \
    remote-settings-git-reader
```

You can test your SSH setup:

```bash
docker run \
    <...chosen approach...>
    remote-settings-git-reader \
    ssh -T git@github.com

Hi <username>! You've successfully authenticated, but GitHub does not provide shell access.
```

## Settings

- ``GIT_REPO_PATH``: the path to the Git repository to use.
- ``SELF_CONTAINED`` (default: `false`): if set to `true`, the application will serve all necessary content from the Git repository, including
  attachments and certificates chains.
- ``ATTACHMENTS_BASE_URL`` (default: `None`): this URL will be used as the base URL for attachments. If `SELF_CONTAINED` is `false`, this URL is mandatory, otherwise the current domain will be used by default (`Host` request header).
