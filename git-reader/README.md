# Remote Settings Over Git

## Building the Docker image

```bash
docker build -t remote-settings-git-reader .
```

## Settings

- ``GIT_REPO_PATH``: the path to the Git repository to use.
- ``SELF_CONTAINED`` (default: `false`): if set to `true`, the application will serve all necessary content from the Git repository, including
  attachments and certificates chains.
- ``CDN_DOMAIN`` (default: `None`): if running behind a CDN, this will ensure that URI rewrites for attachments and certificates will point at the CDN and not the origin server.
- ``ATTACHMENTS_BASE_URL`` (default: `None`): this URL will be used as the base URL for attachments. If `SELF_CONTAINED` is `false`, this URL is required. With self-contained, the current domain will be used by default (`Host` request header) if not set.


## Running the application

We have included a docker-compose file to make running locally easy.

The application needs access to a Git repository containing Remote Settings data (read-only):

```bash
docker compose run git-reader

# OR
docker run --rm -p 8000:8000 \
    -e GIT_REPO_PATH=/mnt/data/latest \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data:ro \
    remote-settings-git-reader
```

But first, we will initialize the folder structure required to execute Git updates atomically.
Use the ``gitupdate`` command and the ``GIT_REPO_URL`` environment variable to specify the repository to clone:

```bash
docker compose run \
    -e GIT_REPO_URL=git@github.com:mozilla/remote-settings-data.git \
    git-reader gitupdate

# OR
docker run --rm \
    -e GIT_REPO_URL=git@github.com:mozilla/remote-settings-data.git \
    -e GIT_REPO_PATH=/mnt/data/latest \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data \
    remote-settings-git-reader gitupdate
```

Unless you used an anonymous clone, this is likely to fail, as the container needs access to the Git repository via SSH.

### Using SSH keys

When cloning the repository anonymously (from `https://...`) the Git LFS is rate-limited and it is very likely that you will hit the limit when pulling the LFS files.

To avoid this, we clone the repository via SSH for authentication.

Since the container is going to regularly run Git fetch commands to keep the repository up to date, you need to let the container use your SSH keys. There are two approaches.

1. Forward the host SSH agent into the container.

This requires to have a SSH agent working on the host. It has the advantage of not requiring the container to have access to the actual key and passphrase (if any).

```bash
docker compose run \
    -e GIT_REPO_URL=git@github.com:mozilla/remote-settings-data.git \
    -e SSH_AUTH_SOCK=/app/ssh-agent \
    -v $SSH_AUTH_SOCK:/app/ssh-agent \
    git-reader gitupdate

# OR
docker run --rm \
    -e GIT_REPO_PATH=/mnt/data/latest \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data \
    -e SSH_AUTH_SOCK=/app/ssh-agent \
    -v $SSH_AUTH_SOCK:/app/ssh-agent \
    remote-settings-git-reader gitupdate
```

2. Or mount the private key file into the container.

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
docker compose run \
    -e GIT_REPO_URL=git@github.com:mozilla/remote-settings-data.git \
    -v `pwd`/ssh-material:/app/.ssh \
    git-reader gitupdate

# OR
docker run --rm \
    -e GIT_REPO_PATH=/mnt/data/latest \
    -e SELF_CONTAINED=true \
    -v /mnt/git/remote-settings-data:/mnt/data \
    -v `pwd`/ssh-material:/app/.ssh \
    remote-settings-git-reader gitupdate
```

You can test your SSH setup:

```bash
docker run \
    <...chosen approach...>
    remote-settings-git-reader \
    ssh -T git@github.com

Hi <username>! You've successfully authenticated, but GitHub does not provide shell access.
```

## Updating the repository

Once the repository is initialized, you can run the ``gitupdate`` command to fetch updates from the remote repository:

For example, every 5 minutes in a cronjob:

```bash
*/5 * * * * docker run ...
```
