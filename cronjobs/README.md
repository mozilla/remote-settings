# Remote Settings Lambdas

A collection of scripts related to the Remote Settings service.

## Sentry

All commands use Sentry to report any unexpected errors. Sentry can be configured with these environment variables, which are recommended, but not required:

- `SENTRY_DSN`: The DSN from the "Client Keys" section in the project settings in Sentry.
- `SENTRY_ENV`: The environment to use for Sentry, e.g. dev, stage or prod.

## Commands

Each command can be run, either with Python:

```
$ python aws_lambda.py validate_signature
```

or via the Docker container:

```
$ docker run remote-settings-lambdas validate_signature
```


### refresh_signature

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``REFRESH_SIGNATURE_AUTH``: credentials, either ``user:pass`` or ``{access-token}`` (default: ``None``)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)
- ``MAX_SIGNATURE_AGE``: Refresh signatures that are older that this age in days (default: ``7``)

> **Note**:
> In order to force refresh of all signatures, set ``MAX_SIGNATURE_AGE=0``

Example:

```
$ REFRESH_SIGNATURE_AUTH=reviewer:pass  python aws_lambda.py refresh_signature

Looking at /buckets/monitor/collections/changes:
Looking at /buckets/source/collections/source: to-review at 2018-03-05 13:56:08 UTC ( 1520258168885 )
Looking at /buckets/staging/collections/addons: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251343 )
Looking at /buckets/staging/collections/certificates: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251441 )
Looking at /buckets/staging/collections/plugins: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251547 )
Looking at /buckets/staging/collections/gfx: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251640 )

```


### backport_records

Backport the changes from one collection to another. This is useful if the new collection (*source*) has become the source of truth,
but there are still clients pulling data from the old collection (*destination*).

> Note: This lambda is not safe if other users can interact with the destination collection.

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``BACKPORT_RECORDS_SOURCE_AUTH``: authentication for source collection
- ``BACKPORT_RECORDS_DEST_AUTH``: authentication for destination collection (default: same as source)
- ``BACKPORT_RECORDS_SOURCE_BUCKET``: bucket id to read records from
- ``BACKPORT_RECORDS_SOURCE_COLLECTION``: collection id to read records from
- ``BACKPORT_RECORDS_SOURCE_FILTERS``: optional filters when backporting records as JSON format (default: none, eg. ``"{"min_age": 42}"``)
- ``BACKPORT_RECORDS_DEST_BUCKET``: bucket id to copy records to (default: same as source bucket)
- ``BACKPORT_RECORDS_DEST_COLLECTION``:collection id to copy records to (default: same as source collection)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)
- ``SAFE_HEADERS``: Add concurrency control headers to update requests (default: ``false``)

Example:

```
$ BACKPORT_RECORDS_SOURCE_AUTH=user:pass BACKPORT_RECORDS_SOURCE_BUCKET=blocklists BACKPORT_RECORDS_SOURCE_COLLECTION=certificates BACKPORT_RECORDS_DEST_BUCKET=security-state BACKPORT_RECORDS_DEST_COLLECTION=onecrl  python3 aws_lambda.py backport_records

Batch #0: PUT /buckets/security-state/collections/onecrl/records/003234b2-f425-eae6-9596-040747dab2b9 - 201
Batch #1: PUT /buckets/security-state/collections/onecrl/records/00ac492e-04f7-ee6d-5fd2-bb12b97a4b7f - 201
Batch #2: DELETE /buckets/security-state/collections/onecrl/records/23 - 200
Done. 3 changes applied.

```

```
$ BACKPORT_RECORDS_SOURCE_AUTH=user:pass BACKPORT_RECORDS_SOURCE_BUCKET=blocklists BACKPORT_RECORDS_SOURCE_COLLECTION=certificates BACKPORT_RECORDS_DEST_BUCKET=security-state BACKPORT_RECORDS_DEST_COLLECTION=onecrl  python3 aws_lambda.py backport_records

Records are in sync. Nothing to do.

```


### sync_megaphone

Send the current version of Remote Settings data to the Push server.

Does nothing if versions are in sync.

Environment config:

- ``SERVER``: Remote Settings server URL (default: ``http://localhost:8888/v1``)
- ``MEGAPHONE_URL``: Megaphone service URL
- ``MEGAPHONE_READER_AUTH``: Bearer token for Megaphone read access
- ``MEGAPHONE_BROADCASTER_AUTH``: Bearer token for Megaphone broadcaster access
- ``BROADCASTER_ID``: Push broadcaster ID (default: ``remote-settings``)
- ``CHANNEL_ID``: Push channel ID (default: ``monitor_changes``)

Example:

```
$ SERVER=https://settings.prod.mozaws.net/v1 MEGAPHONE_URL="https://push.services.mozilla.com/v1" MEGAPHONE_READER_AUTH="a-b-c" MEGAPHONE_BROADCASTER_AUTH="d-e-f" python aws_lambda.py sync_megaphone
```


## Test locally

```
$ make test

$ SERVER=https://firefox.settings.services.mozilla.com/v1/  python aws_lambda.py validate_signature
```

### Local Kinto server

Best way to obtain a local setup that looks like a writable Remote Settings instance is to follow [this tutorial](https://remote-settings.readthedocs.io/en/latest/tutorial-local-server.html)

It is possible to initialize the server with some fake data, like for the Kinto Dist smoke tests:

```
$ bash /path/to/kinto-dist/tests/smoke-test.sh
```

## Releasing

1. Create a release on Github on https://github.com/mozilla-services/remote-settings-lambdas/releases/new
2. Create a new tag `X.Y.Z` (*This tag will be created from the target when you publish this release.*)
3. Generate release notes
4. Publish release

## License 

Apache 2.0

