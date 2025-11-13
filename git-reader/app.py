from __future__ import annotations

import io
import json
import mimetypes
import os
import pathlib
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Awaitable, BinaryIO, Callable, Generator
from urllib.parse import urlparse

import lz4.block
import prometheus_client
import pygit2
from dockerflow import checks
from dockerflow.fastapi import router as dockerflow_router
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


HERE = pathlib.Path(__file__).parent.resolve()
VERSION = "0.0.1"
# The API is served under /v2 prefix since /records endpoints present in /v1
# are not implemented.
API_PREFIX = "v2/"
REMOTE_NAME = "origin"
LFS_POINTER_FILE_SIZE_BYTES = 140
STARTUP_BUNDLE_FILE = "bundles/startup.json.mozlz4"
GIT_REF_PREFIX = "v1/"  # See cronjobs/src/commands/git_export.py
METRICS_PREFIX = "remotesettings"
METRICS = {
    "request_duration_seconds": prometheus_client.Histogram(
        name=f"{METRICS_PREFIX}_request_duration_seconds",
        documentation="Histogram of request duration in seconds",
        labelnames=[
            "method",
            "endpoint",
            "status",
            "bucket_id",
            "collection_id",
        ],
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 3.0, 6.0, float("inf")],
    ),
    "request_summary": prometheus_client.Counter(
        name=f"{METRICS_PREFIX}_request_summary",
        documentation="Counter of requests",
        labelnames=[
            "method",
            "endpoint",
            "status",
            "bucket_id",
            "collection_id",
        ],
    ),
    "repository_age_seconds": prometheus_client.Gauge(
        name=f"{METRICS_PREFIX}_repository_age_seconds",
        documentation="Gauge of repository latest commit age in seconds",
    ),
    "repository_read_latency_seconds": prometheus_client.Histogram(
        name=f"{METRICS_PREFIX}_repository_read_latency_seconds",
        documentation="Histogram of repository read latency in seconds",
        labelnames=["operation"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, float("inf")],
    ),
}

# Augment the default mimetypes with our own.
mimetypes.init(files=[HERE / "mimetypes.txt"])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)
    git_repo_path: str = Field(..., description="Path to the Git repository")
    self_contained: bool = Field(
        False,
        description="Whether to serve `attachments/` and `cert-chains/` endpoints.",
    )
    attachments_base_url: str | None = Field(
        None,
        description="Base URL for attachments. Required if SELF_CONTAINED is false.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    print("Using settings:", settings)
    return settings


@lru_cache(maxsize=1)
def get_repo(settings: Settings = Depends(get_settings)) -> pygit2.Repository:
    if not settings.git_repo_path:
        raise RuntimeError("GIT_REPO_PATH is not set")
    if not os.path.exists(settings.git_repo_path):
        raise RuntimeError(f"GIT_REPO_PATH does not exist: {settings.git_repo_path}")
    try:
        print("Opening git repo at:", settings.git_repo_path)
        repo = pygit2.Repository(settings.git_repo_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to open git repo at {settings.git_repo_path}: {e}"
        ) from e
    return repo


class CollectionNotFound(Exception):
    """
    Raised when a requested collection or bucket is not found.
    """

    pass


class UnknownTimestamp(Exception):
    """Raised when timestamp requested with `_since` is does
    not have any matching tag.
    """

    pass


class LFSPointerFoundError(Exception):
    """Raised when the requested file is a Git LFS pointer file."""

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


"""
See `cronjobs/src/commands/build_bundles.py` for the code that builds the
startup bundle with mozLz4 compression (mozilla lz4 variant).
There is an open bug to use standard lz4 (without magic number)
https://bugzilla.mozilla.org/show_bug.cgi?id=1209390
"""
MOZLZ4_HEADER_MAGIC = b"mozLz40\x00"


def read_json_mozlz4(content: bytes) -> list[dict]:
    """
    Read changesets from a mozLz4 compressed file.
    """
    if not content.startswith(MOZLZ4_HEADER_MAGIC):
        raise ValueError("File does not start with mozLz4 magic number")
    compressed = content[len(MOZLZ4_HEADER_MAGIC) :]
    decompressed = lz4.block.decompress(compressed)
    return json.loads(decompressed.decode("utf-8"))


def write_json_mozlz4(fd: BinaryIO, changesets: list[dict]):
    """
    Write changesets to a mozLz4 compressed file.
    """
    json_str = json.dumps(changesets).encode("utf-8")
    compressed = lz4.block.compress(json_str)
    fd.write(MOZLZ4_HEADER_MAGIC + compressed)


def measure_git_read_time(operation: str):
    """
    Decorator to measure the time spent in Git read operations.
    """

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            global METRICS
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_sec = time.time() - start_time
                METRICS["repository_read_latency_seconds"].labels(
                    operation=operation
                ).observe(elapsed_sec)

        return wrapper

    return decorator


class GitService:
    """
    Wrapper on top of pygit2 to serve content.
    """

    def __init__(self, repo: pygit2.Repository, settings: Settings):
        self.repo = repo
        self.settings = settings

    @staticmethod
    def dep(
        repo: pygit2.Repository = Depends(get_repo),
        settings: Settings = Depends(get_settings),
    ) -> "GitService":
        return GitService(repo, settings)

    def check_content(self):
        """
        Check that the repository has the expected branches and tags.
        """
        branches = {branch_name for branch_name in self.repo.branches.local}
        bucket_branches = {
            branch_name
            for branch_name in branches
            if branch_name.startswith(f"{GIT_REF_PREFIX}buckets/")
        }
        if f"{GIT_REF_PREFIX}common" not in branches:
            raise RuntimeError(
                f"Missing '{GIT_REF_PREFIX}common' branch in repository. Found: {branches}"
            )
        if not bucket_branches:
            raise RuntimeError(
                f"Missing '{GIT_REF_PREFIX}buckets/*' branches in repository. Found: {branches}"
            )

        # Check that the repository has timestamps/* tags.
        timestamp_tags = {
            ref
            for ref in self.repo.references
            if ref.startswith(f"refs/tags/{GIT_REF_PREFIX}timestamps/")
        }
        if not timestamp_tags:
            raise RuntimeError(
                f"Missing '{GIT_REF_PREFIX}timestamps/*' tags in repository. Found: {timestamp_tags}"
            )

        # Check that LFS files are present if self-contained.
        if self.settings.self_contained:
            known_lfs_file = os.path.join(
                self.settings.git_repo_path, "attachments", STARTUP_BUNDLE_FILE
            )
            if os.path.getsize(known_lfs_file) < LFS_POINTER_FILE_SIZE_BYTES:
                raise LFSPointerFoundError(
                    f"{STARTUP_BUNDLE_FILE} is a Git LFS pointer file"
                )

    def get_head_info(self, branch: str = f"{GIT_REF_PREFIX}common") -> dict[str, str]:
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

    @measure_git_read_time(operation="build_changeset")
    def get_collection_changeset(self, bid, cid, _since=None):
        """
        Get the changeset for a specific collection.
        """
        # List all tags for this collection and sort them by timestamp desc.
        refs = sorted(
            [
                ref.decode()
                for ref in self.repo.raw_listall_references()
                if ref.decode().startswith(
                    f"refs/tags/{GIT_REF_PREFIX}timestamps/{bid}/{cid}/"
                )
            ],
            reverse=True,
        )
        if not refs:
            raise CollectionNotFound(bid, cid)

        latest_ref = refs[0]
        timestamp = int(latest_ref.split("/")[-1])

        # 1. Read the collection content at latest timestamp.
        refobj = self.repo.lookup_reference(latest_ref)
        tag = self.repo[refobj.target]
        commit = tag.peel(pygit2.GIT_OBJECT_COMMIT)
        tree = commit.tree

        metadata = None
        records_by_id = {}
        for path, oid in self._scan_folder(tree, path=cid):
            # Get metadata and records from {cid}/ folder.
            bcontent = self.repo[oid].data
            content = json.loads(bcontent.decode("utf-8"))
            if path.endswith("metadata.json"):
                metadata = content
            else:
                # Each record is stored in a separate file named {id}.json
                rid = pathlib.Path(path).stem
                records_by_id[rid] = content
        assert metadata is not None, "metadata.json not found"

        # 2. If _since is provided, compare and hide unchanged records.
        if _since is not None:
            since_ref = f"refs/tags/{GIT_REF_PREFIX}timestamps/{bid}/{cid}/{_since}"
            try:
                old_refobj = self.repo.lookup_reference(since_ref)
            except KeyError:
                # No such tag, this timestamp is unknown.
                raise UnknownTimestamp(_since)

            old_tag = self.repo[old_refobj.target]
            old_commit = old_tag.peel(pygit2.GIT_OBJECT_COMMIT)
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
            # Deleted records are shown as tombstones.
            # Note: we don't have `last_modified` but clients don't need it.
            for rid in old_records_by_id.keys():
                filtered[rid] = {"id": rid, "deleted": True}
            records_by_id = filtered

        # Sort records by last_modified desc.
        changes = sorted(
            records_by_id.values(),
            key=lambda r: r.get("last_modified", 0),
            reverse=True,
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

    def get_server_info(self):
        """
        Get the server information from the common branch.
        """
        bcontent = self._get_file_content("server-info.json")
        content = json.loads(bcontent.decode("utf-8"))
        return content

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

    @measure_git_read_time(operation="scan_folder")
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

    @measure_git_read_time(operation="get_file_content")
    def _get_file_content(
        self, path: str, branch: str = f"{GIT_REF_PREFIX}common"
    ) -> bytes:
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


def clean_since_param(
    _since: str | None = Query(None, alias="_since"),
) -> int | None:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Add a very simple in-memory cache to store data during the app lifespan.
    """
    # This tells dockerflow's version endpoint where to find the app directory.
    app.state.APP_DIR = HERE
    yield {"cache": {}}


app = FastAPI(title="Remote Settings Over Git", lifespan=lifespan, version=VERSION)
app.include_router(dockerflow_router, prefix=f"/{API_PREFIX[:-1]}", tags=["dockerflow"])
app.mount(f"/{API_PREFIX}__metrics__", prometheus_client.make_asgi_app())


@app.middleware("http")
async def requests_metrics(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    global METRICS

    start_time = time.time()
    response = await call_next(request)
    elapsed_sec = time.time() - start_time

    labels = (
        request.method,
        request.scope["route"].name if "route" in request.scope else "unknown",
        response.status_code,
        request.path_params.get("bid", ""),
        request.path_params.get("cid", ""),
    )
    METRICS["request_summary"].labels(*labels).inc()
    METRICS["request_duration_seconds"].labels(*labels).observe(elapsed_sec)

    return response


@checks.register
def git_repo_health() -> list[checks.Check]:
    result = []
    try:
        git = GitService.dep(
            repo=get_repo(settings=get_settings()), settings=get_settings()
        )
        git.check_content()
    except LFSPointerFoundError as exc:
        result.append(checks.Error(str(exc), id="git.health.0002"))
    except Exception as exc:
        print(exc)
        result.append(checks.Error(str(exc), id="git.health.0003"))
    return result


@app.get("/")
def root():
    return RedirectResponse(f"/{API_PREFIX}", status_code=307)


@app.get(f"/{API_PREFIX[:-1]}")
def hello_unsuffixed():
    return RedirectResponse(f"/{API_PREFIX}", status_code=307)


@app.get(f"/{API_PREFIX}", response_model=HelloResponse)
def hello(
    request: Request,
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
) -> str:
    # Determine attachments base URL
    attachments_base_url = settings.attachments_base_url
    if attachments_base_url is None:
        assert settings.self_contained, (
            "ATTACHMENTS_BASE_URL is required when not SELF_CONTAINED"
        )
        attachments_base_url = (
            f"{request.url.scheme}://{request.url.netloc}/{API_PREFIX}attachments"
        )
    if not attachments_base_url.endswith("/"):
        attachments_base_url += "/"

    server_info = git.get_server_info()
    common_branch_info = git.get_head_info(branch=f"{GIT_REF_PREFIX}common")

    repo_age_seconds = int(time.time()) - common_branch_info["timestamp"]
    METRICS["repository_age_seconds"].set(repo_age_seconds)

    return {
        "project_name": server_info["project_name"],
        "project_docs": server_info["project_docs"],
        "http_api_version": "2.0",
        "project_version": app.version,
        "settings": {
            "readonly": True,
        },
        "git": {
            "common": common_branch_info,
        },
        "capabilities": {
            "attachments": {
                **server_info["capabilities"]["attachments"],
                "base_url": attachments_base_url,
            },
        },
    }


@app.get(
    f"/{API_PREFIX}buckets/monitor/collections/changes/changeset",
    response_model=ChangesetResponse,
)
def monitor_changes(
    _expected: int = 0,
    _since: str | None = Depends(clean_since_param),
    bucket: str | None = None,
    collection: str | None = None,
    git: GitService = Depends(GitService.dep),
):
    if _since and _expected > 0 and _expected < _since:
        raise HTTPException(
            status_code=400,
            detail="_expected must be superior to _since if both are provided",
        )

    timestamp, metadata, changes = git.get_monitor_changes_changeset(
        _since=_since, bucket=bucket, collection=collection
    )
    return ChangesetResponse(
        timestamp=timestamp,
        metadata=metadata,
        changes=changes,
    )


@app.get(
    f"/{API_PREFIX}buckets/{{bid}}/collections/{{cid}}/changeset",
    response_model=ChangesetResponse,
)
def collection_changeset(
    request: Request,
    bid: str,
    cid: str,
    _expected: int = 0,
    _since: str | None = Depends(clean_since_param),
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
):
    if _since and _expected > 0 and _expected < _since:
        raise HTTPException(
            status_code=400,
            detail="_expected must be superior to _since if both are provided",
        )

    try:
        timestamp, metadata, changes = git.get_collection_changeset(
            bid, cid, _since=_since
        )
    except CollectionNotFound:
        raise HTTPException(status_code=404, detail=f"{bid}/{cid} not found")
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
        rewritten_x5u = f"{request.url.scheme}://{request.url.netloc}/{API_PREFIX}cert-chains/{parsed.path.lstrip('/')}"
        metadata["signature"]["x5u"] = rewritten_x5u

    return ChangesetResponse(
        timestamp=timestamp,
        metadata=metadata,
        changes=changes,
    )


@app.get(f"/{API_PREFIX}__broadcasts__", response_model=BroadcastsResponse)
def broadcasts(git: GitService = Depends(GitService.dep)):
    return git.get_broadcasts()


@app.get(f"/{API_PREFIX}cert-chains/{{pem:path}}", response_class=PlainTextResponse)
def cert_chain(
    pem: str,
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
):
    if not settings.self_contained:
        raise HTTPException(status_code=404, detail="cert-chains/ not enabled")
    try:
        return git.get_cert_chain(pem)
    except (FileNotFoundError, IsADirectoryError):
        raise HTTPException(status_code=404, detail=f"{pem} not found")


@app.api_route(f"/{API_PREFIX}attachments/{{path:path}}", methods=["GET", "HEAD"])
def attachments(
    request: Request,
    path: str,
    settings: Settings = Depends(get_settings),
    git: GitService = Depends(GitService.dep),
):
    if not settings.self_contained:
        raise HTTPException(status_code=404, detail="attachments/ not enabled")

    base_dir = os.path.join(os.path.realpath(settings.git_repo_path), "attachments")

    # Normalize requested_path
    # Translate '..' and remove redundant separators.
    # This is ugly but CodeQL does not like pathlib.Path.resolve().
    requested_path = os.path.normpath(os.path.join(base_dir, path))

    # Prevent directory traversal: ensure requested_path is inside base_dir
    # See https://codeql.github.com/codeql-query-help/python/py-path-injection/
    if not requested_path.startswith(base_dir):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not os.path.exists(requested_path) or not os.path.isfile(requested_path):
        raise HTTPException(status_code=404, detail=f"Attachment {path} not found")

    # Make sure we won't serve the LFS pointer file to clients.
    if os.path.getsize(requested_path) < LFS_POINTER_FILE_SIZE_BYTES:
        content = open(requested_path, "rb").read()
        if content.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise LFSPointerFoundError(f"{path} is a Git LFS pointer file")

    # The startup bundle contains all collections changesets.
    # Their x5u URLs must be rewritten to point to this server.
    if path == STARTUP_BUNDLE_FILE:
        cached = request.state.cache.get("_cached_startup_bundle")
        current_commit: str = git.get_head_info()["id"]
        if cached != current_commit:
            print("Rewriting x5u URL inside startup bundle")
            # Read from disk
            content = open(requested_path, "rb").read()
            startup_changesets = read_json_mozlz4(content)
            for changeset in startup_changesets:
                x5u = changeset["metadata"]["signature"]["x5u"]
                parsed = urlparse(x5u)
                rewritten_x5u = f"{request.url.scheme}://{request.url.netloc}/{API_PREFIX}cert-chains/{parsed.path.lstrip('/')}"
                changeset["metadata"]["signature"]["x5u"] = rewritten_x5u

            # Dump into memory bytes and cache content to skip rewriting next time.
            buffer = io.BytesIO()
            write_json_mozlz4(buffer, startup_changesets)
            request.state.cache["_cached_startup_content"] = buffer
            request.state.cache["_cached_startup_bundle"] = current_commit

        cached_content: io.BytesIO = request.state.cache["_cached_startup_content"]
        cached_content.seek(0)
        # Stream from memory.
        return StreamingResponse(cached_content, media_type="application/x-mozlz4")

    # Stream from disk
    mimetype, _ = mimetypes.guess_type(requested_path)
    return StreamingResponse(open(requested_path, "rb"), media_type=mimetype)
