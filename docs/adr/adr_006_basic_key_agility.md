# Basic Key Agility

* Status: draft
* Deciders: acottner, mleplatre, skym
* Date: Aug 26, 2025

## Context and Problem Statement

When data is published, a content signature is computed on the server and exposed in the `signature` field of the collection metadata. The client synchronizes its local copy with the server and verifies the signature of the resulting dataset [^1].

[^1]: See [Remote Settings + Autograph](https://docs.google.com/presentation/d/11x0dGRQ-yWzi7cAWYci6NeLN2mYH_Ba6Ml2gn9gOx30/edit?slide=id.p#slide=id.p).

The `signature` field is an object obtained from the Autograph signing response that contains:
- `x5u`: an absolute URL to the certificate chain
- `signature`: the signature value
- `mode`: the key type (`p384ecdsa`)

This model has at least two limitations: strong coupling with Mozilla domains for certificate chains, and lack of flexibility for signatures.

Since the certificate chain URLs are absolute, the client fetches them blindly. And because these URLs point to the Mozilla CDN, self-hosting Remote Settings without relying on Mozilla is not possible. It's also currently not possible to serve the certificate chains from fallback, custom, or alternative domains.

Moreover, since clients consume a single signature, rotating certificate chains requires both chains to be fully interoperable. This will eventually become impossible if we need different key types (e.g., post-quantum signatures).

The goal of this document is to present a new design where signature verification is more flexible.

## Decision Drivers

To choose our solution, we considered the following criteria:

- **Complexity**: Low → High — how complex the solution is
- **Cost of implementation**: Low → High — how much effort it requires
- **Agility**: Low → High — how flexible the solution is
- **Security**: Low → High — impact on security

## Considered Options

1. [Option 0 - Do nothing](#option-0---do-nothing)
2. [Option 1 - Signatures list with x5u relative URLs](#option-1---signatures-list-with-x5u-relative-urls)
3. [Option 2 - Signatures list with rewritten absolute x5u URLs](#option-2---signatures-list-with-rewritten-absolute-x5u-urls)
4. [Option 3 - Full key agility](#option-3---full-key-agility)

## Decision Outcome

Chosen option: **Option 1**. This approach offers some agility with very low effort, while maintaining the same level of security. *Option 2* is less elegant, and *Option 3* requires engineering resources our team doesn't have. *Option 1* paves the way for future improvements and could gradually evolve into the system described in *Option 3*.

## Pros and Cons of the Options

### Option 0 - Do nothing

No changes are made. All clients verify a single signature using absolute URLs. We anticipate abrupt shifts for clients any time we have to change certificates or signature algorithms (e.g., a future post-quantum change).

- **Complexity**: N/A
- **Cost of implementation**: N/A
- **Agility**: Low — cannot use different key chains or serve from different domains
- **Security**: High — everything is under control

### Option 1 - Signatures list with x5u relative URLs

In addition to the `signature` (kept for backward compatibility), this option introduces a new `signatures` field, a list of signature objects with the following fields:

- `x5u`: a **relative** URL to the certificate chain
- `signature`: the signature value
- `mode`: the key type (`p384ecdsa`)

The client iterates through the list until a signature verification succeeds, or throws an error after all fail.

In this first "basic agility" phase, the server still signs the data with a single signature but exposes it to clients as a list — paving the way for a future phase where multiple signatures could be computed on the server.

The full certificate chain is obtained by concatenating a `base_url` field from the server root URL, similar to how it's done for attachments. This allows multiple Remote Settings servers to be hosted under different domains with different base URLs (e.g., fallback domains).

The base URL is hardcoded in the server configuration:

```ini
kinto.signer.certs_chains_base_url = "https://autograph.cdn/"
```

The Autograph signing response still returns an absolute URL, but the base domain is trimmed before storing the signature payload in the collection metadata. For simplicity, the relative URL retains all URL location folders (e.g., `/g/202405/remote-settings/...`).

```python
payload = autograph_service.sign(serialized_data, key_id)
abs_x5u = payload["x5u"]
parsed = urllib.parse(old_x5u)
rel_x5u = parsed.location
payload["x5u"] = rel_x5u

storage.save_collection({"signature": payload, ...})
```

- **Complexity**: Low — simple and does not introduce extra complexity
- **Cost of implementation**: Low — server changes are trivial; client changes are relatively straightforward assuming all signatures use the same type (`ECDSA-p384`). Most effort goes into migrating to the new `signatures` field and updating tests/documentation so only legacy clients reference the old `signature` field.
- **Agility**: Mid — clients can now use fallback signatures. However, they still expect the root certificate to be Mozilla's and all signatures to use the same type.
- **Security**: High — unchanged security model. The base URL comes from the server and is stored in memory. Signature verification fails if `x5u` leads to a 404 or if the chain's root certificate doesn't match Mozilla's.

Client-side implementation might look like this:

```js
const {
  capabilities: {
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
    console.log("Try next signature...");
  }
}
throw new InvalidSignatureError();
```

> **Note:** Currently, the `signer` part of the `kinto_remote_settings` plugin is not enabled on reader nodes.
> That's why the base URL is exposed under the `changes` capabilities instead of `signer`.
> If needed, the plugin initialization code could be adjusted to eliminate this split and expose the necessary info cleanly under `signer`.

### Option 2 - Signatures list with rewritten absolute x5u URLs

This approach is similar to *Option 1*, but instead of trimming the domain from the absolute URL, it replaces it with another configured value.

```ini
kinto.signer.certs_chains_base_url = "https://custom.com/"
```

In the server view that serves the collection changesets, the `x5u` is rewritten on the fly:

```python
def view_changeset(bucket, collection):
    metadata = storage.get_collection_metadata(bucket, collection)

    custom_base = settings["kinto.signer.certs_chains_base_url"]
    old_x5u = metadata["signature"]["x5u"]
    parsed = urllib.parse(old_x5u)

    new_x5u = custom_base + parsed.location

    metadata["signature"]["x5u"] = new_x5u

    return {
      "metadata": metadata,
      ...
    }
```

- **Complexity**: Mid-Low — still simple, but URL rewriting on the fly is less elegant than using relative URLs
- **Cost of implementation**: Low — server changes are trivial, and clients still rely on absolute URLs transparently. Less code change than *Option 1*
- **Agility**: Mid-Low — fallback signatures are possible and servers are decoupled from Mozilla domains, but this approach may complicate plans to serve Remote Settings from git data due to the need to replicate rewriting logic
- **Security**: High — the security model remains unchanged

### Option 3 - Full key agility

Since *Option 1* and *Option 2* still require all signatures to share the same key type, we could imagine a redesigned client-side verification that supports full key agility.

Each signature in the list would carry all necessary information for the client to validate it. For example, currently the client does not use the `mode` field (ECDSA-P384, post-quantum, RSA key pair). We could also add a root certificate identifier or any extra field needed by the client.

- **Complexity**: Mid-Low — Autograph would provide the necessary attributes; architecturally not a big increase in complexity
- **Cost of implementation**: High — major changes on both client and server. Client-side would require deep knowledge of the NSS stack to implement new verification methods (in C)
- **Agility**: High — provides full key agility
- **Security**: High — the current model, which relies on hardcoded root certificates, would need to be redesigned, and the new model would require a full security assessment
