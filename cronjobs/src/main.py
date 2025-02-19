#!/usr/bin/env python
import glob
import importlib
import os
import sys

import sentry_sdk
from sentry_sdk.integrations.gcp import GcpIntegration
from decouple import config

HERE = os.path.dirname(os.path.realpath(__file__))

SENTRY_DSN = config("SENTRY_DSN", default=None)
SENTRY_ENV = config("SENTRY_ENV", default=None)
SERVER_URL = os.getenv("SERVER", "http://localhost:8888/v1")

if SENTRY_DSN:
    # Note! If you don't do `sentry_sdk.init(DSN)` it will still work
    # to do things like calling `sentry_sdk.capture_exception(exception)`
    # It just means it's a noop.
    env_option = {}
    if SENTRY_ENV:
        env_option = {"environment": SENTRY_ENV}

    # We're running in Google Cloud. See https://cloud.google.com/functions/docs/configuring/env-var
    sentry_sdk.init(SENTRY_DSN, integrations=[GcpIntegration()], **env_option)


def help_(**kwargs):
    """Show this help."""

    def white_bold(s):
        return f"\033[1m\x1b[37m{s}\033[0;0m"

    entrypoints = [
        os.path.splitext(os.path.basename(f))[0] for f in glob.glob(f"{HERE}/commands/[a-z]*.py")
    ]
    commands = [
        getattr(importlib.import_module(f"commands.{entrypoint}"), entrypoint)
        for entrypoint in entrypoints
    ]
    func_listed = "\n - ".join([f"{white_bold(f.__name__)}: {f.__doc__}" for f in commands])
    print(
        f"""
Remote Settings lambdas.

Available commands:

 - {func_listed}
    """
    )


def run(command, event=None, context=None):
    if event is None:
        event = {"server": SERVER_URL}
    if context is None:
        context = {"sentry_sdk": sentry_sdk}

    if isinstance(command, (str,)):
        # Import the command module and returns its main function.
        mod = importlib.import_module(f"commands.{command}")
        command = getattr(mod, command)

    # Note! If the sentry_sdk was initialized with the platform integration,
    # it is now ready to automatically capture all and any unexpected exceptions.
    # See https://docs.sentry.io/platforms/python/guides/aws-lambda/
    # See https://docs.sentry.io/platforms/python/guides/gcp-functions/

    # Option to test failure to test Sentry integration.
    if event.get("force_fail") or os.getenv("FORCE_FAIL"):
        raise Exception("Found forced failure flag")

    command(event, context)


def backport_records(*args, **kwargs):
    return run("backport_records", *args, **kwargs)


def blockpages_generator(*args, **kwargs):
    return run("blockpages_generator", *args, **kwargs)


def refresh_signature(*args, **kwargs):
    return run("refresh_signature", *args, **kwargs)


def sync_megaphone(*args, **kwargs):
    return run("sync_megaphone", *args, **kwargs)


def build_bundles(*args, **kwargs):
    return run("build_bundles", *args, **kwargs)


def main(*args):
    # Run the function specified in CLI arg.
    #
    # $ AUTH=user:pass python aws_lambda.py refresh_signature
    #

    if not args or args[0] in ("help", "--help"):
        help_()
        return
    entrypoint = args[0]
    try:
        command = globals()[entrypoint]
    except KeyError:
        print(f"Unknown function {entrypoint!r}", file=sys.stderr)
        help_()
        return 1
    command()


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
