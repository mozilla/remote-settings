import base64
import hashlib
import itertools
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable

import jwt
import requests
from decouple import config
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


HTTP_TIMEOUT_CONNECT_SECONDS = config(
    "HTTP_TIMEOUT_CONNECT_SECONDS", default=10, cast=int
)
HTTP_TIMEOUT_READ_SECONDS = config("HTTP_TIMEOUT_READ_SECONDS", default=60, cast=int)
HTTP_TIMEOUT_WRITE_SECONDS = config("HTTP_TIMEOUT_WRITE_SECONDS", default=600, cast=int)
HTTP_RETRY_DELAY_SECONDS = config("HTTP_RETRY_DELAY_SECONDS", default=1, cast=float)
HTTP_RETRY_MAX_COUNT = config("HTTP_RETRY_MAX_COUNT", default=10, cast=int)
MAX_PARALLEL_REQUESTS = config("MAX_PARALLEL_REQUESTS", default=10, cast=int)
HTTP_TIMEOUT_SECONDS = (HTTP_TIMEOUT_CONNECT_SECONDS, HTTP_TIMEOUT_READ_SECONDS)
HTTP_TIMEOUT_BATCH_SECONDS = (HTTP_TIMEOUT_CONNECT_SECONDS, HTTP_TIMEOUT_READ_SECONDS)
HTTP_TIMEOUT_UPLOAD_SECONDS = (HTTP_TIMEOUT_CONNECT_SECONDS, HTTP_TIMEOUT_WRITE_SECONDS)
SLOW_DOWN_SECONDS = config("SLOW_DOWN_SECONDS", default=3, cast=int)


GITHUB_MAX_LFS_BATCH_SIZE = config("GITHUB_MAX_LFS_BATCH_SIZE", default=100, cast=int)


def fetch_and_hash(url, dest_file=None):
    """
    Fetch from the given URL and return the contents' sha256 hash and size.
    """
    if dest_file is None:
        dest_file = os.devnull

    print("Fetch attachment %r" % url)
    h = hashlib.sha256()
    total = 0
    with open(dest_file, "wb") as f:
        with requests.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1024 * 64):
                if not chunk:
                    continue
                f.write(chunk)
                h.update(chunk)
                total += len(chunk)
    return h.hexdigest(), total


def _new_retrying_session() -> requests.Session:
    """
    Session tuned for GitHub LFS 'batch' and 'verify' calls.
    """
    session = requests.Session()
    retries = Retry(
        total=HTTP_RETRY_MAX_COUNT,
        connect=HTTP_RETRY_MAX_COUNT,
        read=HTTP_RETRY_MAX_COUNT,
        backoff_factor=1.5,
        status_forcelist=[408, 409, 425, 429, 500, 502, 503, 504],
        allowed_methods={"HEAD", "GET", "PUT", "POST", "DELETE", "OPTIONS", "TRACE"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=MAX_PARALLEL_REQUESTS)
    session.mount("https://", adapter)
    return session


def github_lfs_batch_request(
    auth_header: str,
    objects: Iterable[dict[str, Any]],
    operation: str,  # "upload" or "download",
    repo_owner: str,
    repo_name: str,
    timeout: float = HTTP_TIMEOUT_BATCH_SECONDS,
) -> dict[str, Any]:
    """
    Generic Git LFS Batch call.
    objects: [{"oid": "<sha256-hex>", "size": <int>}, ...]

    https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md#requests
    """
    url = f"https://github.com/{repo_owner}/{repo_name}.git/info/lfs/objects/batch"
    headers = {
        "Accept": "application/vnd.git-lfs+json",
        "Content-Type": "application/vnd.git-lfs+json",
        "Authorization": auth_header,
    }
    payload = {
        "operation": operation,
        "transfers": ["basic"],
        "objects": list(objects),
    }
    session = _new_retrying_session()
    r = session.post(url, headers=headers, json=payload, timeout=timeout)
    if r.status_code != 200:
        print(f"LFS: batch failed with status {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def _download_from_cdn_and_upload_to_lfs_volume(
    source: tuple[str, int, str],  # (sha256_hex, size, src_url)
    dest: tuple[str, str, dict[str, str]],  # (href, method, headers),
    retry_max_count: int = HTTP_RETRY_MAX_COUNT,
    retry_delay: float = HTTP_RETRY_DELAY_SECONDS,
    timeout: float = HTTP_TIMEOUT_UPLOAD_SECONDS,
) -> None:
    """
    Downloads the file locally (verifies digest/size), then uploads to specified URL.
    """
    sha256_hex, size, src_url = source
    upload_href, upload_method, upload_headers = dest

    with tempfile.NamedTemporaryFile() as tmp:
        tmp_path = tmp.name
        retry = 0
        while retry < retry_max_count:
            # Download from CDN into temp file.
            downloaded_digest, downloaded_size = fetch_and_hash(
                src_url, dest_file=tmp_path
            )
            if downloaded_size == size and downloaded_digest == sha256_hex:
                break
            retry += 1
            time.sleep(retry_delay)
        else:
            raise RuntimeError(
                f"LFS: {src_url} failed to download after {retry_max_count} attempts"
            )
        # If we reach here, it means we successfully downloaded the file from the CDN.
        # Now, upload it to LFS volume.
        print(
            f"LFS: uploading {src_url} -> {upload_method} {upload_href} ({size} bytes)"
        )
        with open(tmp_path, "rb") as f:
            resp = requests.request(
                upload_method.upper(),
                upload_href,
                data=f,
                headers=upload_headers,
                timeout=timeout,
            )
        if not resp.ok:
            print(f"LFS: {src_url} upload failed with {resp.status_code}: {resp.text}")
        resp.raise_for_status()


def _github_lfs_verify_upload(
    source: tuple[str, str],  # (sha256_hex, size)
    dest: tuple[str, dict[str, str, str]],  # (href, method, headers)
    timeout: float = HTTP_TIMEOUT_SECONDS,
) -> None:
    """
    The LFS upload API returns a verify action that the client has to call in
    order to complete the upload process.
    """
    oid, size = source
    verify_href, method, headers = dest
    payload = {"oid": oid, "size": size}
    r = requests.request(
        method, verify_href, json=payload, headers=headers, timeout=timeout
    )
    if r.status_code not in (200, 201, 204):
        print(f"LFS: verify for {oid} failed with {r.status_code}: {r.text}")
    r.raise_for_status()


def _base64_auth_header(username: str, token: str) -> str:
    creds = f"{username}:{token}".encode("utf-8")
    return f"Basic {base64.b64encode(creds).decode('ascii')}"


def _create_app_jwt(app_id: str, private_key_path: str) -> str:
    with open(private_key_path, "r") as f:
        private_key = f.read()

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": app_id,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


def _resolve_installation_id(jwt_token: str, repo_owner: str, repo_name: str) -> str:
    """
    Resolves the installation ID for the GitHub App on the given repo.
    """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/installation"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    if r.status_code != 200:
        print(f"Failed to resolve installation ID: {r.status_code} {r.text}")
    r.raise_for_status()
    data = r.json()
    installation_id = data.get("id")
    if not installation_id:
        raise RuntimeError("GitHub App is not installed on the repository")
    return str(installation_id)


def _mint_installation_access_token(
    jwt_token: str, installation_id: str
) -> tuple[str, str]:
    """
    Mints an installation access token for the given installation ID.
    """
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.post(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    if r.status_code != 201:
        print(f"Failed to mint installation token: {r.status_code} {r.text}")
    r.raise_for_status()
    data = r.json()
    token = data.get("token")
    expires_at = data.get("expires_at")
    if not token or not expires_at:
        raise RuntimeError("Failed to obtain installation access token")
    return token, expires_at


def _verify_personal_token(username: str, token: str) -> dict[str, Any]:
    """
    Verifies that the personal access token is valid by fetching the user info.
    """
    url = "https://api.github.com/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    if resp.status_code != 200:
        print(f"Failed to verify personal token: {resp.status_code} {resp.text}")
    resp.raise_for_status()
    return resp.json()


def _verify_installation_token(
    token: str, repo_owner: str, repo_name: str
) -> dict[str, Any]:
    """
    Verifies that the installation token can access the given repository.
    """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    if r.status_code != 200:
        print(f"Failed to verify installation token: {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()


def github_lfs_validate_credentials(
    repo_owner: str,
    repo_name: str,
    # Option A: Personal Access Token (PAT)
    github_username: str | None = None,
    github_token: str | None = None,
    # Option B: GitHub App authentication
    github_app_id: str | None = None,
    github_app_private_key_path: str | None = None,
    timeout: float = HTTP_TIMEOUT_BATCH_SECONDS,
) -> str:
    """
    Test GitHub LFS credentials by making a dummy batch request.
    """
    if github_username and github_token:
        if not github_token.startswith("github_pat_"):
            print(
                "Warning: It looks like the provided GitHub token is not a PAT (personal access token)."
            )
        authz = _base64_auth_header(github_username, github_token)
        user_data = _verify_personal_token(github_username, github_token)
        print(
            f"Authenticated as GitHub user: {user_data.get('login')} (id={user_data.get('id')})"
        )

    elif github_app_id and github_app_private_key_path:
        # For LFS, use Basic with username 'x-access-token' and the installation token as the password.
        # private key -> JWT -> installation ID -> installation token -> Basic auth with token
        # See https://docs.github.com/en/rest/reference/apps#authentication
        jwt_token = _create_app_jwt(github_app_id, github_app_private_key_path)
        installation_id = _resolve_installation_id(jwt_token, repo_owner, repo_name)
        installation_token, expires_at = _mint_installation_access_token(
            jwt_token, installation_id
        )
        print(
            f"Issued installation access token (installation_id={installation_id}) expiring at {expires_at}"
        )
        repo_info = _verify_installation_token(
            installation_token, repo_owner, repo_name
        )
        print(
            f"Installation token can access repo: {repo_info.get('full_name')} (id={repo_info.get('id')})"
        )
        authz = _base64_auth_header("x-access-token", installation_token)

    github_lfs_batch_request(
        auth_header=authz,
        objects=[{"oid": "a" * 64, "size": 42}],  # dummy object
        operation="upload",
        repo_owner=repo_owner,
        repo_name=repo_name,
        timeout=timeout,
    )

    return authz


def github_lfs_batch_upload_many(
    objects: Iterable[tuple[str, int, str]],  # (sha256_hex, size, source_url),
    repo_owner: str,
    repo_name: str,
    auth_header: str,
    max_parallel_requests: int = MAX_PARALLEL_REQUESTS,
) -> None:
    """
    Performs LFS batch 'upload' for up to GITHUB_MAX_LFS_BATCH_SIZE objects per batch,
    PUTs missing objects to the presigned destinations, and POSTs verify if provided.

    objects: iterable of (oid_hex:str, size:int, src_url:str)
    """
    chunks = list(itertools.batched(objects, GITHUB_MAX_LFS_BATCH_SIZE))
    total_chunks = len(chunks)

    # Single session for batch/verify calls (NOT reused for presigned PUTs/POSTs)
    for idx, chunk in enumerate(chunks, start=1):
        print(f"LFS: uploading chunk {idx}/{total_chunks} ({len(chunk)} objects)")

        batch_resp = github_lfs_batch_request(
            auth_header=auth_header,
            objects=[{"oid": oid, "size": size} for (oid, size, _url) in chunk],
            operation="upload",
            repo_owner=repo_owner,
            repo_name=repo_name,
        )

        # Map response objects by oid
        resp_objects = batch_resp.get("objects") or []
        api_objs_by_oid = {o.get("oid"): o for o in resp_objects if o.get("oid")}

        # Decide which to upload or/and verify
        to_upload: list[tuple[tuple[str, int, str], tuple[str, dict[str, str]]]] = []
        to_verify: list[tuple[tuple[str, int], tuple[str, str, dict[str, str]]]] = []
        for oid, size, url in chunk:
            api_obj = api_objs_by_oid.get(oid)
            if not api_obj:
                print(
                    f"LFS: warning: server omitted oid {oid} in batch response; skipping"
                )
                continue
            if err := api_obj.get("error"):
                print(
                    f"LFS: upload error for {oid}: {err.get('code')} {err.get('message')}"
                )
                continue
            act = api_obj.get("actions") or {}
            upload_action = act.get("upload")
            if upload_action:
                href = upload_action["href"]
                method = upload_action.get("method") or "PUT"
                headers = upload_action["header"]
                to_upload.append(((oid, size, url), (href, method, headers)))
            else:
                print(f"LFS: already present {url} ({oid}) on server, skipping upload.")

            # The server returns a verify endpoint with headers.
            verify_action = act.get("verify")
            if verify_action:
                href = verify_action["href"]
                headers = verify_action["header"]
                to_verify.append(((oid, size), (href, "POST", headers)))
            else:
                print(f"LFS: no verify action for {oid}, skipping verify.")

        # Parallel uploads
        if to_upload:
            with ThreadPoolExecutor(max_workers=max_parallel_requests) as pool:
                futures = [
                    pool.submit(_download_from_cdn_and_upload_to_lfs_volume, src, dest)
                    for (src, dest) in to_upload
                ]
                for f in as_completed(futures):
                    f.result()  # propagate exceptions

        # Parallel verifications
        with ThreadPoolExecutor(max_workers=max_parallel_requests) as pool:
            futures = [
                pool.submit(_github_lfs_verify_upload, src, dest)
                for (src, dest) in to_verify
            ]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

        print(
            f"LFS: {len(to_upload)} uploaded and {len(to_verify)} verified in chunk {idx}/{total_chunks}"
        )
        time.sleep(SLOW_DOWN_SECONDS) # avoid hitting rate limits
