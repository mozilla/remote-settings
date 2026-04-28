import logging
import re
from collections import defaultdict

import requests
from kinto.core.errors import raise_invalid
from kinto.core.events import AfterResourceChanged, ResourceChanged
from kinto.core.utils import read_env


logger = logging.getLogger(__name__)


def qualname(obj):
    return str(obj.__class__).split("'")[1]


def _match(pattern, value):
    if pattern.startswith("^"):
        return re.match(pattern, value) is not None
    return pattern == value


def _get_slack_hooks(storage, context):
    bucket_id = context["bucket_id"]
    collection_id = context["collection_id"]
    bucket_uri = "/buckets/%s" % bucket_id

    if context["resource_name"] == "collection":
        metadata = next(
            impacted["old"] if context["action"] == "delete" else impacted["new"]
            for impacted in context["impacted_objects"]
        )
    else:
        metadata = storage.get(
            parent_id=bucket_uri, resource_name="collection", object_id=collection_id
        )

    if "kinto-slack" not in metadata:
        metadata = storage.get(
            parent_id="", resource_name="bucket", object_id=bucket_id
        )

    return metadata.get("kinto-slack", {}).get("hooks", [])


def get_messages(storage, context):
    hooks = _get_slack_hooks(storage, context)
    filters = ("action", "resource_name", "id", "record_id", "collection_id", "event")
    messages = []

    for hook in hooks:
        conditions_met = all(
            field not in hook
            or field not in context
            or _match(hook[field], context[field])
            for field in filters
        )
        if not conditions_met:
            continue

        messages.append(
            {
                "channel": hook["channel"],
                "text": hook["template"].format_map(defaultdict(str, context)),
            }
        )

    return messages


def build_notification(event):
    resource_name = event.payload["resource_name"]
    storage = event.request.registry.storage
    context = dict(
        root_url=event.request.route_url("hello"),
        client_address=event.request.client_addr,
        impacted_objects=event.impacted_objects,
        event=qualname(event),
        **event.payload,
    )
    context.setdefault("record_id", "{record_id}")
    context.setdefault("collection_id", "{collection_id}")

    messages = []
    for impacted in event.impacted_objects:
        _context = context.copy()
        obj = impacted.get("new", impacted.get("old"))
        _context[resource_name + "_id"] = _context["id"] = obj["id"]
        messages += get_messages(storage, _context)

    setattr(event.request, "_kinto_slack_messages", messages)


def send_notification(event):
    messages = getattr(event.request, "_kinto_slack_messages", [])
    if not messages:
        return

    settings = event.request.registry.settings
    webhook_url = settings.get("slack.webhook_url")
    if not webhook_url:
        logger.warning("slack.webhook_url is not configured")
        return

    for msg in messages:
        try:
            resp = requests.post(webhook_url, json=msg, timeout=5)
            resp.raise_for_status()
        except Exception:
            logger.exception("Could not send Slack notification")


def _validate_slack_settings(event):
    for impacted in event.impacted_objects:
        if event.payload["action"] == "delete":
            continue
        obj = impacted.get("new", {})
        hooks = obj.get("kinto-slack", {}).get("hooks", [])
        for hook in hooks:
            if "channel" not in hook:
                raise_invalid(
                    event.request,
                    name="kinto-slack",
                    description="Hook is missing 'channel'",
                )
            if "template" not in hook:
                raise_invalid(
                    event.request,
                    name="kinto-slack",
                    description="Hook is missing 'template'",
                )


def includeme(config):
    settings = config.get_settings()
    webhook_url = settings.get("slack.webhook_url")
    webhook_url = read_env("kinto.slack.webhook_url", webhook_url)
    config.add_settings({"slack.webhook_url": webhook_url})

    config.add_api_capability(
        "slack",
        "Slack notifications plugin for Kinto",
        "https://github.com/mozilla/remote-settings/blob/main/kinto-slack/",
    )

    config.add_subscriber(
        _validate_slack_settings,
        ResourceChanged,
        for_resources=("bucket", "collection"),
        for_actions=("create", "update"),
    )

    config.add_subscriber(
        build_notification, ResourceChanged, for_resources=("record", "collection")
    )
    config.add_subscriber(
        send_notification, AfterResourceChanged, for_resources=("record", "collection")
    )
