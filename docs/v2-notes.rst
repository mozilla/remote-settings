.. _v2-notes:

Version 2 Endpoints
===================

Version 2 of the remote-settings reader endpoints started going live in late 2025.
Clients will begin transitioning to them in early 2026.


Why V2?
-------

V2 routes are served by the git-reader service, which provides several advantages compared to using a full service in a read-only mode:

1. Simplifies the hosting/deploying of reader nodes
    a. No database is required for reads
    b. Far fewer dependencies to worry about
2. Allow for down-stream changes
    a. It's now possible to remove a specific collection (even modify if content signing is setup).
    b. Useful in enterprise environments, or even firefox forks
3. Prevent clients from using non-optimized routes
    a. All kinto routes are served by the v1 readers, but most are not used
4. Allows for specific reader releases
    a. Changes that impact just the admin UI or writers will not require a reader release


Breaking Changes
----------------
We are changing the format of one parameter, ``_expected``, which was wrapped in quotes in V1 routes. V2 routes will expect an unwrapped integer as a timestamp. V1 is being made forward-compatible to not require the quotes, so future clients will be able to switch API versions forth without issue.


Hosting a V2 Reader
-------------------

Please see the `git-reader readme <https://github.com/mozilla/remote-settings/blob/main/git-reader/README.md>`_ for instructions.
