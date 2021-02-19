.. _introduction:

What is Remote Settings?
========================

Basically, Remote Settings consists of two components: a remote server (REST API) powered by `Kinto <https://github.com/Kinto/kinto>`_ and a client (Gecko API).

Everything is done via a collection of records that is kept in sync between the client local database and the remote data.

.. note::

    See also `The History of Remote Settings <https://blog.mathieu-leplatre.info/the-history-of-firefox-remote-settings.html>`_


Why is it better than building my own?
--------------------------------------

Out of the box you get for free:

- Multi-signoff
- Syncing of data - real time push based updates
- Content signing - your data is signed server side and verified on the client side transparently
- File attachment support
- Target filtering (JEXL a-la Normandy)
- Telemetry


What does the workflow look like?
---------------------------------

Once your collection is setup, a typical workflow would be:

1. Connect to the UI on the VPN
2. Make some changes
3. Request a review (with an optional comment)

The people designated as reviewers will receive a notification email.

4. As a reviewer, you can preview the changes in a real browser
5. Once you verified that the changes have the expected effects, you can approve (or reject) the changes from the Admin UI
6. Changes will then be pulled by every Firefox clients on their next synchronization


What does the client API look like?
-----------------------------------

On the client side, listen for changes via an event listener:

.. code-block:: javascript

    const { RemoteSettings } = ChromeUtils.import("resource://services-settings/remote-settings.js", {});

    RemoteSettings("my-collection")
      .on("sync", (e) => {
        const { created, updated, deleted } = e.data;
        /*
          updated == [

            {
              old: {label: "Yahoo",  enabled: true,  weight: 10, id: "d0782d8d", last_modified: 1522764475905},
              new: {label: "Google", enabled: true,  weight: 20, id: "8883955f", last_modified: 1521539068414},
            },
          ]
         */
      });


Or get the current list of local records:

.. code-block:: javascript

    const records = await RemoteSettings("my-collection").get();
    /*
      records == [
        {label: "Yahoo",  enabled: true,  weight: 10, id: "d0782d8d", last_modified: 1522764475905},
        {label: "Google", enabled: true,  weight: 20, id: "8883955f", last_modified: 1521539068414},
        {label: "Ecosia", enabled: false, weight: 5,  id: "337c865d", last_modified: 1520527480321},
      ]
    */

.. note::

    * `Client API full reference <https://firefox-source-docs.mozilla.org/services/common/services/RemoteSettings.html>`_


What does the server side API look like?
----------------------------------------

If you want, like our `Web UI <https://github.com/Kinto/kinto-admin>`_, to rely on the REST API for your integration, the :ref:`multi-signoff tutorial <tutorial-multi-signoff>` gives a good overview.

Basically, creating a record would look like this:

.. code-block:: bash

    curl -X POST ${SERVER}/buckets/main-workspace/collections/${COLLECTION}/records \
         -H 'Content-Type:application/json' \
         -d "{\"data\": {\"property\": $i}}" \
         -u us3r:p455w0rd

Requesting review:

.. code-block:: bash

    curl -X PATCH ${SERVER}/buckets/main-workspace/collections/${COLLECTION} \
         -H 'Content-Type:application/json' \
         -d '{"data": {"status": "to-review"}}' \
         -u us3r:p455w0rd

Approving changes:

.. code-block:: bash

    curl -X PATCH ${SERVER}/buckets/main-workspace/collections/${COLLECTION} \
         -H 'Content-Type:application/json' \
         -d '{"data": {"status": "to-sign"}}' \
         -u us3r:p455w0rd

And the record is now published:

.. code-block:: bash

    curl ${SERVER}/buckets/main/collections/${COLLECTION}/records

.. note::

    * `Kinto REST API reference <https://kinto.readthedocs.io/en/latest/api/1.x/index.html#full-reference>`_
    * `Python client <https://github.com/Kinto/kinto-http.py>`_
    * `JavaScript client <https://github.com/Kinto/kinto-http.js>`_


Awesome! How do I get started?
------------------------------

You'll find out :ref:`in the next chapter <getting-started>`!
