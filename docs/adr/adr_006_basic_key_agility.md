# Basic Key Agility

* Status: draft
* Deciders: acottner, mleplatre, skym
* Date: Aug 26, 2025

## Context and Problem Statement

When data is published, a content signature is computed on the server and
exposed in the ``signature`` field of the collection metadata.
The client synchronizes its local copy with the server and verifies the signature
of the resulting dataset.

The `signature` field is an object obtained from the Autograph signing response that contains:
- `x5u`: an absolute URL to the certificate chain
- `signature`: the signature value
- `mode`: the key type (`p384ecdsa`)

This model has at least two limitations: strong coupling with Mozilla domains for certificate chains,
and lack of flexibility for signatures.

Since the certificate chains URLs are absolute, the client fetches them blindly. And because
these URLs point to the Mozilla CDN, self-hosting Remote Settings without dependency to Mozilla
is not possible. It is also currently not possible to serve the certificate chains from fallback, custom,
or alternative domains.

And since the clients consume a single signature, rotating certificates chains implies
both chains to be fully interoperable. This will eventually become impossible if we need
different key types (e.g. post-quantum signatures).

The goal of this document is to present a new design where signature verification is
more flexible.

## Decision Drivers

In order to choose our solution we considered the following criteria:

- **Complexity**: Low → High: how complex is the solution
- **Cost of implementation**: Low → High: how much efforts does it represent
- **Agility**: Low → High: how flexible is the solution
- **Security**: Low → High: impact on security

## Considered Options

1. [Option 0 - Do nothing](#option-0---do-nothing)
1. [Option 1 - Signatures list with x5u relative URLs](#option-1---signatures-list-with-x5u-relative-urls)
1. [Option 2 - Signatures list with rewritten absolute x5u URLs](#option-2---signatures-list-with-rewritten-absolute-x5u-urls)
1. [Option 3 - Full key agility](#option-3---full-key-agility)

## Decision Outcome

Chosen option: **Option 1**. This approach offers some agility with very low efforts, while maintaining the same level of security. *Option 2* is less elegant, and *Option 3* requires engineering resources that our team doesn't have. *Option 1* paves the way for future improvements, and could gradually be turned into the system that is described in *Option 3*.

## Pros and Cons of the Options

### Option 0 - Do nothing

No change is made. All clients verify a single signature using absolute URLs. We anticipate that there will be abrupt shifts for clients any time we have to change certificates or signature algorithms (eg. a future post-quantum change).

- **Complexity**: N/A
- **Cost of implementation**: N/A
- **Agility**: Low: cannot use different key chains, cannot serve from different domain
- **Security**: High: everything under control

### Option 1 - Signatures list with x5u relative URLs

In addition to the `signature` that would have to be kept for backwards compatibility, this option consists in
adding a new ``signatures`` field, as a list of signatures objects, with the following fields:

- `x5u`: a **relative** URL to the certificate chain
- `signature`: the signature value
- `mode`: the key type (`p384ecdsa`)

The client will iterate the list until the signature verification is successful, and throw the error once all were tried.
In this first "basic agility" phase, the server is still going to sign the data with a single signature, but it will be exposed to the clients as a list, paving the way for the future phase where multiple signatures could be computed on the
server.

The full certificate chain is obtained by concatenating a `base_url` field obtained from the server root URL, like it is done for attachments. With this solution, we can host several Remote Settings servers under different domains with different base URLs (e.g. fallback domains).

The exposed based URL would be hardcoded on the server configuration:

```ini
kinto.signer.certs_chains_base_url = "https://autograph.cdn/"
```

The Autograph signing response would still return the absolute URL, but the base URL domain
would be trimmed from it before storing the signature payload in the collection metadata.
For simplicity, the relative URL will keep all the URL location folders (eg. `/g/202405/remote-settings/...`).

```python
payload = autograph_service.sign(serialized_data, key_id)
abs_x5u = payload["x5u"]
parsed = urllib.parse(old_x5u)
rel_x5u = parsed.location
payload["x5u"] = rel_x5u

storage.save_collection({"signature": payload, ...})
```

- **Complexity**: Low: This solution is simple and does not introduce extra complexity.
- **Cost of implementation**: Low: The changes on the server for this first phase are trivial. The changes on clients (desktop and Rust) are also relatively straightforward, since it is assumed that all signatures have the same type (`ECDSA-p384`). A large proportion of the work to be done is related to migrating the ecosystem to the new `signatures` field and adjusting unit tests and documentation, so that only legacy clients source code refers to the old `signature` field.
- **Agility**: Mid: With this solution, the clients can now have fallback signatures in case the first one fails. They still expect the root certificate of the chains to be Mozilla's root, and they still expect all signatures to have the same type.
- **Security**: High: The security model hasn't changed. The base URL comes from the server, and is stored in memory. The signature will fail if the `x5u` leads to a 404 or if the root certificate of the fetched chain does not match Mozilla's.

The client implementation would roughly look like this:

```js
const {
  capabilites: {
    changes: {
      certs_chains_base_url: baseUrl
    }
  }
} = await client.getServerInfo();

for (const signInfo of metadata.signatures) {
  const x5u = baseUrl + signInfo.x5u;
  const pem = await (await fetch(x5u)).text();  // Likely already cached
  try {
    await verifier.verify(serializedRecords, signInfo.signature, pem);
    return true;
  } catch (err) {
    console.log(`Try next signature...`);
  }
}
throw new InvalidSignatureError();
```

> **Note:** currently the `signer` part of the `kinto_remote_settings` plugin is not enabled on reader nodes.
> That's why we expose the base URL in the `changes` capabilities instead of the `signer` one.
> If that is considered an issue, the initialization code of the `kinto_remote_settings` plugin could be adjusted
> to remove this split and always expose the necessary info elegantly under `signer`.


### Option 2 - Signatures list with rewritten absolute x5u URLs

The approach is the same as *Option 1* for the list of signatures, but instead of trimming the domain
from the absolute URL, it can be replaced by another configured value.

```ini
kinto.signer.certs_chains_base_url = "https://custom.com/"
```

On the server, in the view that serves collections changesets, the `x5u` is rewritten on the fly.

```py
def view_changeset(bucket, collection):
    metadata = storage.get_collection_metadata(bucket, collection)

    custom_base = settings["kinto.signer.certs_chains_base_url"]
    old_x5u = metadata["signature"]["x5u"]
    parsed = urllib.parse(old_x5u)

    new_x5u = custom_base + parsed.location

    metatadata["signature"]["x5u"] = new_x5u

    return {
      "metadata": metadata,
      ...
    }
```

- **Complexity**: Mid-Low: This solution is simple and does not introduce extra complexity, however rewriting URLs on the fly is less elegant than using relative URLs.
- **Cost of implementation**: Low: The changes on the server are trivial, and client still relies on absolute URLs transparently. This represents less code changes than *Option 1*.
- **Agility**: Mid-Low: Like with *Option 1*, clients have fallback signatures and the Remote Settings server is decoupled from Mozilla domains. However, in the context of our plans to serve Remote Settings from git data, this would imply to also have this rewritten logic in the new service layer.
- **Security**: High: The security model hasn't changed.


### Option 3 - Full key agility

Since *Option 1* or *Option 2* still rely on a list of signatures that share the same key type, we could
imagine a completely revamped signature verification client code that would provide full agility.

Each signature of the list would carry all necessary information to qualify the expected key verification.
For example, currently the client does not use the `mode` field (ECDSA-P384, post-quantum, RSA key pair).
We could add a root certificate identifier or any extra field required for the client signature verification implementation.

- **Complexity**: Mid-Low: Autograph would be in charge of providing the necessary attributes to support the client implementation. In terms of architecture, this would not represent a major complexity increase.
- **Cost of implementation**: High: both server and client implementation are greatly impacted. Implementing the client changes would require advanced knowledge of our NSS stack, since new verification methods would have to be implemented (in C).  
- **Agility**: High: Unlike other options, this would provide full key agility.
- **Security**: High: The current security model that relies on hard-coded root certificates in the client would have to be redesigned, and would require performing security assessments for this new model.
