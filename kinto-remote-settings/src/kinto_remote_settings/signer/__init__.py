import copy
import functools
import re
import sys

from kinto.core import metrics as core_metrics
from kinto.core import utils as core_utils
from pyramid.authorization import Authenticated
from pyramid.events import ApplicationCreated
from pyramid.settings import aslist

from .. import __version__
from .events import ReviewApproved, ReviewRejected, ReviewRequested
from .utils import storage_create_raw


DEFAULT_SETTINGS = {
    "allow_floats": False,
    "auto_create_resources": False,
    "auto_create_resources_principals": [Authenticated],
    "resources": "/buckets/main-workspace -> /buckets/main-preview -> /buckets/main",
    "signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
    "to_review_enabled": False,
    "hard_delete_destination_on_source_deletion": False,
}


def on_review_approved(event):
    metrics_service = event.request.registry.metrics
    if metrics_service is not None:
        count = event.changes_count
        bid = event.resource["destination"]["bucket"]
        cid = event.resource["destination"]["collection"]
        # Report into a global counter.
        metrics_service.count("plugins.signer.approved_changes", count)
        # Report for this collection.
        metrics_service.count(f"plugins.signer.approved_changes.{bid}.{cid}", count)


def includeme(config):
    # We import stuff here, so that kinto-signer can be installed with `--no-deps`
    # and used without having this Pyramid ecosystem installed.
    import transaction
    from kinto.core.events import ACTIONS, ResourceChanged
    from pyramid.events import NewRequest
    from pyramid.settings import asbool

    from . import listeners, utils
    from .backends import heartbeat

    # Register heartbeat to check signer integration.
    config.registry.heartbeats["signer"] = heartbeat

    # Load settings from KINTO_SIGNER_* environment variables.
    settings = config.get_settings()
    for setting, default_value in DEFAULT_SETTINGS.items():
        settings[f"signer.{setting}"] = utils.get_first_matching_setting(
            setting_name=setting,
            settings=settings,
            prefixes=["signer."],
            default=default_value,
        )

    # Check source and destination resources are configured.
    resources = utils.parse_resources(settings["signer.resources"])

    # Expand the resources with the ones that come from per-bucket resources
    # and have specific settings.
    # For example, consider the case where resource is ``/buckets/dev -> /buckets/prod``
    # and there is a setting ``signer.dev.recipes.signer_backend = foo``
    output_resources = resources.copy()
    for key, resource in resources.items():
        # If collection is not None, there is nothing to expand :)
        if resource["source"]["collection"] is not None:
            continue
        bid = resource["source"]["bucket"]
        # Match setting names like signer.stage.specific.autograph.hawk_id
        matches = [
            (v, re.search(rf"signer\.{bid}\.([^\.]+)\.(.+)", k))
            for k, v in settings.items()
        ]
        found = [(v, m.group(1), m.group(2)) for (v, m) in matches if m]
        # Expand the list of resources with the ones that contain collection
        # specific settings.
        for setting_value, cid, setting_name in found:
            signer_key = f"/buckets/{bid}/collections/{cid}"
            if signer_key not in output_resources:
                specific = copy.deepcopy(resource)
                specific["source"]["collection"] = cid
                specific["destination"]["collection"] = cid
                if "preview" in specific:
                    specific["preview"]["collection"] = cid
                output_resources[signer_key] = specific
            output_resources[signer_key][setting_name] = setting_value
    resources = output_resources

    # Determine which are the settings that apply to all buckets/collections.
    global_settings = {
        "editors_group": "{collection_id}-editors",
        "reviewers_group": "{collection_id}-reviewers",
        "to_review_enabled": asbool(settings["signer.to_review_enabled"]),
    }

    # For each resource that is configured, we determine what signer is
    # configured and what are the review settings.
    # Note: the `resource` values are mutated in place.
    config.registry.signers = {}
    for signer_key, resource in resources.items():
        bid = resource["source"]["bucket"]
        server_wide = "signer."
        bucket_wide = f"signer.{bid}."
        prefixes = [bucket_wide, server_wide]

        per_bucket_config = resource["source"]["collection"] is None

        if not per_bucket_config:
            cid = resource["source"]["collection"]
            collection_wide = f"signer.{bid}.{cid}."
            deprecated = f"signer.{bid}_{cid}."
            prefixes = [collection_wide, deprecated, *prefixes]

        # Instantiates the signers associated to this resource.
        dotted_location = utils.get_first_matching_setting(
            "signer_backend",
            settings,
            prefixes,
            default=DEFAULT_SETTINGS["signer_backend"],
        )
        signer_module = config.maybe_dotted(dotted_location)
        backend = signer_module.load_from_settings(settings, prefixes=prefixes)
        config.registry.signers[signer_key] = backend

        # Check if review enabled/disabled for this particular resources.
        resource_to_review_enabled = asbool(
            utils.get_first_matching_setting(
                "to_review_enabled",
                settings,
                prefixes,
                default=global_settings["to_review_enabled"],
            )
        )
        # Keep the `to_review_enabled` field in the resource object
        # only if it was overriden. In other words, this will be exposed in
        # the capabilities if the resource's review setting is different from
        # the global server setting.
        if resource_to_review_enabled != global_settings["to_review_enabled"]:
            resource["to_review_enabled"] = resource_to_review_enabled
        else:
            resource.pop("to_review_enabled", None)

    # Expose the capabilities in the root endpoint.
    exposed_resources = [
        core_utils.dict_subset(
            r, ["source", "destination", "preview", "to_review_enabled"]
        )
        for r in resources.values()
    ]
    message = "Digital signatures for integrity and authenticity of records."
    docs = "https://github.com/Kinto/kinto-signer#kinto-signer"
    config.add_api_capability(
        "signer",
        message,
        docs,
        version=__version__,
        resources=exposed_resources,
        # Backward compatibility with < v26
        group_check_enabled=True,
        **global_settings,
    )

    config.add_subscriber(on_review_approved, ReviewApproved)

    config.add_subscriber(
        functools.partial(listeners.set_work_in_progress_status, resources=resources),
        ResourceChanged,
        for_resources=("record",),
    )

    config.add_subscriber(
        functools.partial(
            listeners.check_collection_status, resources=resources, **global_settings
        ),
        ResourceChanged,
        for_actions=(ACTIONS.CREATE, ACTIONS.UPDATE),
        for_resources=("collection",),
    )

    config.add_subscriber(
        functools.partial(listeners.check_collection_tracking, resources=resources),
        ResourceChanged,
        for_actions=(ACTIONS.CREATE, ACTIONS.UPDATE),
        for_resources=("collection",),
    )

    config.add_subscriber(
        functools.partial(
            listeners.create_editors_reviewers_groups,
            resources=resources,
            editors_group=global_settings["editors_group"],
            reviewers_group=global_settings["reviewers_group"],
        ),
        ResourceChanged,
        for_actions=(ACTIONS.CREATE,),
        for_resources=("collection",),
    )

    config.add_subscriber(
        functools.partial(listeners.cleanup_preview_destination, resources=resources),
        ResourceChanged,
        for_actions=(ACTIONS.DELETE,),
        for_resources=("collection",),
    )

    config.add_subscriber(
        functools.partial(listeners.prevent_collection_delete, resources=resources),
        ResourceChanged,
        for_actions=(ACTIONS.DELETE,),
        for_resources=("collection",),
    )

    if not asbool(settings["signer.allow_floats"]):
        config.add_subscriber(
            functools.partial(listeners.prevent_float_value, resources=resources),
            ResourceChanged,
            for_actions=(ACTIONS.CREATE, ACTIONS.UPDATE),
            for_resources=("record",),
        )

    sign_data_listener = functools.partial(
        listeners.sign_collection_data, resources=resources, **global_settings
    )
    timed_listener = core_metrics.listener_with_timer(
        config, "plugins.signer", sign_data_listener
    )

    config.add_subscriber(
        timed_listener,
        ResourceChanged,
        for_actions=(ACTIONS.CREATE, ACTIONS.UPDATE),
        for_resources=("collection",),
    )

    def on_new_request(event):
        """Send the kinto-signer events in the before commit hook.
        This allows database operations done in subscribers to be automatically
        committed or rolledback.
        """
        # Since there is one transaction per batch, ignore subrequests.
        if hasattr(event.request, "parent"):
            return
        current = transaction.get()
        current.addBeforeCommitHook(listeners.send_signer_events, args=(event,))

    config.add_subscriber(on_new_request, NewRequest)

    try:
        from kinto_emailer import send_notification

        config.add_subscriber(send_notification, ReviewRequested)
        config.add_subscriber(send_notification, ReviewApproved)
        config.add_subscriber(send_notification, ReviewRejected)
    except ImportError:  # pragma: no cover
        pass

    # Automatically create resources on startup if option is enabled.
    def auto_create_resources(event, resources):
        storage = event.app.registry.storage
        permission = event.app.registry.permission
        write_principals = aslist(
            event.app.registry.settings["signer.auto_create_resources_principals"]
        )

        for resource in resources.values():
            perms = {"write": write_principals}
            bucket = resource["source"]["bucket"]
            collection = resource["source"]["collection"]

            bucket_uri = f"/buckets/{bucket}"
            storage_create_raw(
                storage_backend=storage,
                permission_backend=permission,
                resource_name="bucket",
                parent_id="",
                object_uri=bucket_uri,
                object_id=bucket,
                permissions=perms,
            )

            # If resource is configured for specific collection, create it too.
            if collection:
                collection_uri = f"{bucket_uri}/collections/{collection}"
                storage_create_raw(
                    storage_backend=storage,
                    permission_backend=permission,
                    resource_name="collection",
                    parent_id=bucket_uri,
                    object_uri=collection_uri,
                    object_id=collection,
                    permissions=perms,
                )

    # Create resources on startup (except when executing `migrate`).
    if (
        asbool(settings.get("signer.auto_create_resources", False))
        and "migrate" not in sys.argv
    ):
        config.add_subscriber(
            functools.partial(
                auto_create_resources,
                resources=resources,
            ),
            ApplicationCreated,
        )
