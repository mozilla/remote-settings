import os

import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from .conftest import RemoteSettingsClient


# -- BEGIN Webdriver code imported from Telescope
# https://github.com/mozilla-services/telescope/blob/20e8179cb453a4e2d8dd354a0c60aa489a6a8d9f/checks/remotesettings/firefox_sync.py

FIREFOX_BINARY_PATH = os.getenv("FIREFOX_BINARY_PATH")
GECKODRIVER_BINARY_PATH = os.getenv("GECKODRIVER_BINARY_PATH")

# Scripts are executed in the privileged (chrome) context of the browser.
JS_SYNC_SCRIPT = """
const resolve = arguments[arguments.length - 1];
const { RemoteSettings } = ChromeUtils.importESModule(
  "resource://services-settings/remote-settings.sys.mjs"
);
(async () => {
  let error = null;
  try {
    await RemoteSettings.pollChanges({ trigger: "manual" });
  } catch (e) {
    error = `${e.name}: ${e.message}`;
  }
  let inspect = null;
  try {
    inspect = await RemoteSettings.inspect();
  } catch (e) {
    error = error || `${e.name}: ${e.message}`;
  }
  resolve({ ok: error === null, error, inspect });
})();
"""

RUST_SYNC_SCRIPT = """
const resolve = arguments[arguments.length - 1];
const [names] = arguments;
const { SharedRemoteSettingsService } = ChromeUtils.importESModule(
  "resource://gre/modules/RustSharedRemoteSettingsService.sys.mjs"
);
(async () => {
  try {
    const service = SharedRemoteSettingsService.rustService();
    const clients = {};
    for (const name of names) {
      clients[name] = await service.makeClient(name);
    }
    // Synchronizes our clients, and those created by Firefox itself.
    const synced = await service.sync();
    const collections = {};
    for (const name of synced) {
      const client = clients[name] ?? (await service.makeClient(name));
      const records = await client.getRecords(false);
      collections[name] = {
        lastModified: await client.getLastModifiedTimestamp(),
        records: records?.length ?? null,
      };
    }
    const missing = names.filter(name => !synced.includes(name));
    const error = missing.length ? `Not synchronized: ${missing.join(", ")}` : null;
    resolve({ ok: error === null, error, synced, collections });
  } catch (e) {
    resolve({ ok: false, error: `${e.name}: ${e.message}` });
  }
})();
"""

SCRIPTS = {"js": JS_SYNC_SCRIPT, "rust": RUST_SYNC_SCRIPT}


def sync_from_browser(
    server: str, script: str, args: list, timeout_seconds: int
) -> dict:
    options = Options()
    options.binary_location = FIREFOX_BINARY_PATH
    options.add_argument("-headless")
    options.set_preference("services.settings.server", server)
    options.set_preference("services.settings.loglevel", "debug")
    service = Service(
        executable_path=GECKODRIVER_BINARY_PATH,
        env={
            **os.environ,
            # Allow executing scripts in the privileged (chrome) context.
            "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS": "1",
            # Allow overriding the server URL in release builds.
            "MOZ_REMOTE_SETTINGS_DEVTOOLS": "1",
        },
    )
    driver = webdriver.Firefox(options=options, service=service)
    try:
        driver.set_script_timeout(timeout_seconds)
        with driver.context(driver.CONTEXT_CHROME):
            return driver.execute_async_script(script, *args)
    finally:
        driver.quit()


# -- END Webdriver code imported from Telescope


@pytest.mark.readonly
@pytest.mark.skipif(
    not (FIREFOX_BINARY_PATH and GECKODRIVER_BINARY_PATH),
    reason="FIREFOX_BINARY_PATH and GECKODRIVER_BINARY_PATH must be set",
)
@pytest.mark.parametrize(
    "script", [JS_SYNC_SCRIPT, RUST_SYNC_SCRIPT], ids=["js", "rust"]
)
def test_firefox_sync(
    server: str,
    script: str,
    setup_client: RemoteSettingsClient | None,
    anonymous_client: RemoteSettingsClient,
) -> None:
    if setup_client:
        # We run integration-tests with `setup_client: True` on local
        # servers, and CI on pull-requests.
        # We skip the synchronization from a real server for now
        # because we don't a real V2 server yet (See RMST-620).

        # We will only run this test on STAGE for the deploy gateway
        # that promotes the build to PROD if successful.

        # TODO/Notes:
        # - Writer https://remote-settings.allizom.org is only /v1/
        # - V2 reader at https://firefox.settings.services.allizom.org blocks
        #   is behind CDN + WAF, thus blocks __heartbeat__ and has latency
        #   (would not test data from freshly deployed stack)
        # - V2 reader on the origin is not detected as STAGE by the JS client
        #   code (see https://searchfox.org/firefox-main/rev/6d6f414f5ed/services/settings/Utils.sys.mjs#148-150)
        #   and signature verification will fail.
        # - run.sh waits on __heartbeat__
        pytest.skip("Setup credentials provided, not a deployed environment.")

    cid = anonymous_client.collection_name
    result = sync_from_browser(server, script, [[cid]], timeout_seconds=30)

    assert result["ok"], result
