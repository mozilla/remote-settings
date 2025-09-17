from __future__ import annotations

import json
import os
import pathlib
import subprocess
import threading
import time
from datetime import datetime
from functools import lru_cache
from typing import Generator, Optional
from urllib.parse import urlparse

import pygit2
from fastapi import BackgroundTasks, Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PREFIX = "/v1"
REMOTE_NAME = "origin"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    git_repo_path: str
    fetch_interval_seconds: int = 120
    self_contained: bool = False
    attachments_base_url: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_repo() -> pygit2.Repository:
    settings = get_settings()
    if not settings.git_repo_path:
        raise RuntimeError("GIT_REPO_PATH is not set")
    if not os.path.exists(settings.git_repo_path):
        raise RuntimeError(f"GIT_REPO_PATH does not exist: {settings.git_repo_path}")
    # TODO: check that directory is writable (for git fetch)
    try:
        print("Opening git repo at:", settings.git_repo_path)
        repo = pygit2.Repository(settings.git_repo_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to open git repo at {settings.git_repo_path}: {e}"
        ) from e
    # TODO: inspect that we have the expected branches (common, bucket/*)
    # and at least a tag on the common branch.
    # TODO: if self contained, inspect that actual LFS files are here, not pointers.
    return repo


class CollectionNotFound(Exception):
    pass


class UnknownTimestamp(Exception):
    pass


class HelloResponse(BaseModel):
    project_version: str = Field(description="Project version")
    git: dict[str, dict] = Field(description="Git branches info")
    capabilities: dict[str, dict] = Field(description="API capabilities")


class BroadcastsResponse(BaseModel):
    broadcasts: dict[str, str] = Field(description="Broadcasts")
    code: int = Field(description="HTTP status code")


class ChangesetResponse(BaseModel):
    timestamp: int = Field(description="")
    metadata: dict = Field(description="")
    changes: list[dict] = Field(description="")


class GitService:
    """
    Wrapper on top of pygit2 to serve content.
    """

    def __init__(self, repo: pygit2.Repository, settings: Settings):
        self.repo = repo
        self.settings = settings
        self._last_fetch_time = time.time()
        self._fetch_lock = threading.Lock()

    @staticmethod
    def dep(
        repo: pygit2.Repository = Depends(get_repo),
        settings: Settings = Depends(get_settings),
    ) -> "GitService":
        return GitService(repo, settings)

    def fetch_updates(self):
        """
        Fetch updates from the remote repository.
        """
        now = time.time()
        with self._fetch_lock:
            if (now - self._last_fetch_time) < self.settings.fetch_interval_seconds:
                # Already running, or too soon.
                return

            self._last_fetch_time = now

            repo_path = self.settings.git_repo_path
            subprocess.run(["git", "-C", repo_path, "fetch", REMOTE_NAME], check=True)
            # Prune any stale tracking refs
            subprocess.run(
                ["git", "-C", repo_path, "remote", "prune", REMOTE_NAME], check=True
            )
            # Pack/gc to keep the repo lean (safe for bare or non-bare)
            subprocess.run(["git", "-C", repo_path, "gc", "--prune=now"], check=True)
            # Optional extra packing
            subprocess.run(["git", "-C", repo_path, "repack", "-Ad"], check=True)
            if self.settings.self_contained:
                # Fetch files from LFS volume
                subprocess.run(["git", "-C", repo_path, "lfs", "pull"], check=True)
                # Check that everything is valid
                subprocess.run(["git", "-C", repo_path, "lfs", "fsck"], check=True)

            # Reload the repository content.
            self.repo = pygit2.Repository(repo_path)

    def get_head_info(self, branch: str = "common") -> dict[str, str]:
        """
        Get the HEAD information for a specific branch.
        """
        refobj = self.repo.lookup_reference(f"refs/heads/{branch}")
        commit = self.repo[refobj.target]
        return {
            "id": str(commit.id),
            "timestamp": commit.commit_time,
            "datetime": datetime.fromtimestamp(commit.commit_time).isoformat(),
        }

    def get_collection_changeset(self, bid, cid, _since=None):
        """
        Get the changeset for a specific collection.
        """
        refs = sorted(
            [
                ref.decode()
                for ref in self.repo.raw_listall_references()
                if ref.decode().startswith(f"refs/tags/timestamps/{bid}/{cid}")
            ],
            reverse=True,
        )
        if not refs:
            raise CollectionNotFound(bid, cid)

        latest_ref = refs[0]
        timestamp = int(latest_ref.split("/")[-1])

        refobj = self.repo.lookup_reference(latest_ref)
        tag = self.repo[refobj.target]
        commit = tag.peel(pygit2.GIT_OBJECT_COMMIT)
        tree = commit.tree

        metadata = None
        records_by_id = {}
        for path, oid in self._scan_folder(tree, path=cid):
            # Get records.
            bcontent = self.repo[oid].data
            content = json.loads(bcontent.decode("utf-8"))
            if path.endswith("metadata.json"):
                metadata = content
            else:
                rid = pathlib.Path(path).stem
                records_by_id[rid] = content
        assert metadata is not None, "metadata.json not found"

        if _since is not None:
            # Compare current content with the content at _since timestamp.
            since_ref = f"refs/tags/timestamps/{bid}/{cid}/{_since}"
            try:
                old_refobj = self.repo.lookup_reference(since_ref)
            except KeyError:
                raise UnknownTimestamp(_since)
            old_commit = self.repo[old_refobj.target]
            old_tree = old_commit.tree

            old_records_by_id = {}
            for path, oid in self._scan_folder(old_tree, path=cid):
                if not path.endswith("metadata.json"):
                    bcontent = self.repo[oid].data
                    content = json.loads(bcontent.decode("utf-8"))
                    rid = pathlib.Path(path).stem
                    old_records_by_id[rid] = content

            filtered = {}
            for rid, record in records_by_id.items():
                old_record = old_records_by_id.pop(rid, None)
                if old_record is None:
                    filtered[rid] = record
                elif old_record != record:
                    filtered[rid] = record
            for rid in old_records_by_id.keys():
                filtered[rid] = {"id": rid, "deleted": True}
            records_by_id = filtered

        # Sort records by last_modified desc.
        changes = sorted(
            records_by_id.values(), key=lambda r: r["last_modified"], reverse=True
        )
        return timestamp, metadata, changes

    def get_monitor_changes_changeset(self, _since=None, collection=None, bucket=None):
        """
        This is a specific case, since it is stored as a single file in the common branch.
        """
        bcontent = self._get_file_content("monitor-changes.json")
        content = json.loads(bcontent.decode("utf-8"))
        timestamp, metadata, changes = (
            content["timestamp"],
            content["metadata"],
            content["changes"],
        )

        if _since is not None:
            changes = [c for c in changes if c["last_modified"] > _since]

        if collection is not None:
            changes = [c for c in changes if c["collection"] == collection]

        if bucket is not None:
            changes = [c for c in changes if c["bucket"] == bucket]

        return timestamp, metadata, changes

    def get_broadcasts(self):
        """
        Get the broadcasts from the common branch.
        """
        bcontent = self._get_file_content("broadcasts.json")
        content = json.loads(bcontent.decode("utf-8"))
        return content

    def get_cert_chain(self, pem: str) -> str:
        """
        Get the certificate chain for a specific PEM file.
        """
        bcontent = self._get_file_content(f"cert-chains/{pem}")
        content = bcontent.decode("utf-8")
        return content

    def _scan_folder(
        self, tree: pygit2.Tree, path: str
    ) -> Generator[tuple[str, pygit2.Oid], None, None]:
        """
        Scan a folder in the repository and return the list of files.
        """
        for entry in tree:
            if entry.name == path:
                if entry.type != pygit2.GIT_OBJECT_TREE:
                    raise ValueError(f"Path is not a folder: {path}")
                folder_tree = self.repo[entry.id]
                for subentry in folder_tree:
                    if subentry.type == pygit2.GIT_OBJECT_BLOB:
                        yield subentry.name, subentry.id

    def _get_file_content(self, path: str, branch: str = "common") -> bytes:
        """
        Get the content of a file in the repository.
        """
        refobj = self.repo.lookup_reference(f"refs/heads/{branch}")
        commit = self.repo[refobj.target]
        node = commit.tree

        parts = [p for p in path.strip("/").split("/") if p]
        for i, name in enumerate(parts):
            try:
                entry = node[name]
            except KeyError:
                raise FileNotFoundError(f"File not found: {path}")

            obj = self.repo[entry.id]

            if i < len(parts) - 1:
                if entry.type == pygit2.GIT_OBJECT_BLOB:
                    raise FileNotFoundError(
                        f"Path component '{name}' is a file, not a directory: {path}"
                    )
                node = obj  # descend into the subtree
            else:
                if entry.type != pygit2.GIT_OBJECT_BLOB:
                    raise IsADirectoryError(f"Path is a directory, not a file: {path}")
                return obj.data


app = FastAPI(title="Remote Settings Over Git", version="0.0.1")


def clean_since_param(
    _since: Optional[str] = Query(None, alias="_since"),
) -> Optional[int]:
    if _since is None:
        return None
    if not (_since.startswith('"') and _since.endswith('"')):
        raise HTTPException(
            status_code=422,
            detail='Invalid format for _since. Must be quoted integer, e.g. "123"',
        )
    inner = _since.strip('"')
    if not inner.isdigit():
        raise HTTPException(
            status_code=422,
            detail="Invalid format for _since. Must contain only digits inside quotes",
        )
    return int(inner)


@app.get(f"{PREFIX}/", response_model=HelloResponse)
def hello(
    request: Request,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
) -> str:
    # Trigger fetch every 5 updates
    background.add_task(git.fetch_updates)

    # Determine attachments base URL
    attachments_base_url = settings.attachments_base_url
    if attachments_base_url is None:
        assert settings.self_contained, (
            "ATTACHMENTS_BASE_URL is required when not SELF_CONTAINED"
        )
        attachments_base_url = (
            f"{request.url.scheme}://{request.url.netloc}{PREFIX}/attachments"
        )
    if not attachments_base_url.endswith("/"):
        attachments_base_url += "/"

    return {
        "project_version": app.version,
        "git": {
            "common": git.get_head_info(branch="common"),
        },
        "capabilities": {
            "attachments": {
                "base_url": attachments_base_url,
            },
        },
    }


@app.get(
    f"{PREFIX}/buckets/monitor/collections/changes/changeset",
    response_model=ChangesetResponse,
)
def monitor_changes(
    _expected: Optional[str] = Query(None, alias="_expected"),
    _since: Optional[str] = Depends(clean_since_param),
    bucket: Optional[str] = Query(None, alias="bucket"),
    collection: Optional[str] = Query(None, alias="collection"),
    git: GitService = Depends(GitService.dep),
):
    timestamp, metadata, changes = git.get_monitor_changes_changeset(
        _since=_since, bucket=bucket, collection=collection
    )
    # TODO: return 400 if _since > _expected
    return ChangesetResponse(
        timestamp=timestamp,
        metadata=metadata,
        changes=changes,
    )


@app.get(
    f"{PREFIX}/buckets/{{bid}}/collections/{{cid}}/changeset",
    response_model=ChangesetResponse,
)
def collection_changeset(
    request: Request,
    bid: str = Path(...),
    cid: str = Path(...),
    _expected: Optional[str] = Query(None, alias="_expected"),
    _since: Optional[str] = Depends(clean_since_param),
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
):
    try:
        timestamp, metadata, changes = git.get_collection_changeset(
            bid, cid, _since=_since
        )
    except UnknownTimestamp:
        print(
            f"Unknown _since timestamp: {_since} for {bid}/{cid}, falling back to full changeset"
        )
        without_since = request.url.remove_query_params("_since")
        return RedirectResponse(without_since, status_code=307)

    if settings.self_contained:
        # Certificate chains are served from this server.
        x5u = metadata["signature"]["x5u"]
        parsed = urlparse(x5u)
        rewritten_x5u = f"{request.url.scheme}://{request.url.netloc}{PREFIX}/cert-chains/{parsed.path.lstrip('/')}"
        metadata["signature"]["x5u"] = rewritten_x5u

    return ChangesetResponse(
        timestamp=timestamp,
        metadata=metadata,
        changes=changes,
    )


@app.get(f"{PREFIX}/__broadcasts__", response_model=BroadcastsResponse)
def broadcasts(git: GitService = Depends(GitService.dep)):
    return git.get_broadcasts()


@app.get(f"{PREFIX}/cert-chains/{{pem:path}}", response_class=PlainTextResponse)
def cert_chain(
    pem: str = Path(...),
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
):
    if not settings.self_contained:
        raise HTTPException(status_code=404, detail="cert-chains/ not enabled")
    try:
        return git.get_cert_chain(pem)
    except (FileNotFoundError, IsADirectoryError):
        raise HTTPException(status_code=404, detail=f"{pem} not found")


@app.get(f"{PREFIX}/attachments/{{path:path}}")
def attachments(
    path: str = Path(...),
    settings: Settings = Depends(get_settings),
):
    if not settings.self_contained:
        raise HTTPException(status_code=404, detail="attachments/ not enabled")

    base_dir = pathlib.Path(settings.git_repo_path) / "attachments"
    requested_path = (base_dir / os.path.normpath(path)).resolve()

    # Prevent directory traversal: ensure requested_path is inside base_dir
    if not str(requested_path).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail=f"Attachment {path} not found")

    # Stream from disk
    return StreamingResponse(open(requested_path, "rb"))
