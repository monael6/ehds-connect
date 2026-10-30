// Browser side of the security-key signature: WebAuthn (FIDO2 key, NFC badge, Touch ID) or a simulated
// P-256 key created with WebCrypto. Simulated private keys live only in this tab's memory, never in storage.
import { keyRegistrationOptions, registerKey, signChallenge, type SecurityKey, type SignatureProof } from "@/api";

const b64url = (buf: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromB64url = (s: string) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
const softwareKeys = new Map<string, CryptoKey>();

export const webauthnAvailable = () => typeof window !== "undefined" && !!window.PublicKeyCredential && !!navigator.credentials;
export const hasSoftwareKey = (id: string) => softwareKeys.has(id);

type Json = Record<string, unknown>;
function creationOptions(o: Json): PublicKeyCredentialCreationOptions {
  const user = o["user"] as Json;
  return { ...(o as object), challenge: fromB64url(o["challenge"] as string), user: { ...(user as object), id: fromB64url(user["id"] as string) },
    excludeCredentials: ((o["excludeCredentials"] as Json[] | undefined) ?? []).map((c) => ({ ...(c as object), id: fromB64url(c["id"] as string) })) } as unknown as PublicKeyCredentialCreationOptions;
}
function requestOptions(o: Json): PublicKeyCredentialRequestOptions {
  return { ...(o as object), challenge: fromB64url(o["challenge"] as string),
    allowCredentials: ((o["allowCredentials"] as Json[] | undefined) ?? []).map((c) => ({ ...(c as object), id: fromB64url(c["id"] as string) })) } as unknown as PublicKeyCredentialRequestOptions;
}

async function signSoftware(key: CryptoKey, challenge: string) {
  return b64url(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(challenge)));
}

export async function enrolKey(kind: "webauthn" | "software", label: string, recoveryCode?: string): Promise<SecurityKey> {
  const opts = await keyRegistrationOptions(recoveryCode);
  if (kind === "software") {
    const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, false, ["sign", "verify"]);
    const spki = await crypto.subtle.exportKey("spki", pair.publicKey);
    const key = await registerKey({ kind, label, challenge: opts.challenge, public_key: b64url(spki), signature: await signSoftware(pair.privateKey, opts.challenge), recovery_code: recoveryCode || null });
    softwareKeys.set(key.id, pair.privateKey);
    return key;
  }
  const cred = (await navigator.credentials.create({ publicKey: creationOptions(opts.webauthn) })) as PublicKeyCredential | null;
  if (!cred) throw new Error("No security key was used.");
  const r = cred.response as AuthenticatorAttestationResponse;
  const credential = { id: cred.id, rawId: b64url(cred.rawId), type: cred.type, clientExtensionResults: {},
    response: { clientDataJSON: b64url(r.clientDataJSON), attestationObject: b64url(r.attestationObject), transports: r.getTransports?.() ?? [] } };
  return registerKey({ kind, label, challenge: opts.challenge, credential, recovery_code: recoveryCode || null });
}

/** Asks the backend for a one-time challenge bound to this letter and signs it with the chosen key. */
export async function signLetterChallenge(letterId: string, key: SecurityKey): Promise<SignatureProof> {
  const ch = await signChallenge(letterId);
  if (key.kind === "software") {
    const priv = softwareKeys.get(key.id);
    if (!priv) throw new Error("This simulated key is not available in this browser tab. Report it lost and use your backup key, or ask IT for a recovery code.");
    return { key_id: key.id, challenge: ch.challenge, signature: await signSoftware(priv, ch.challenge) };
  }
  if (!ch.webauthn) throw new Error("No hardware key registered.");
  const cred = (await navigator.credentials.get({ publicKey: requestOptions(ch.webauthn) })) as PublicKeyCredential | null;
  if (!cred) throw new Error("No security key was used.");
  const r = cred.response as AuthenticatorAssertionResponse;
  const assertion = { id: cred.id, rawId: b64url(cred.rawId), type: cred.type, clientExtensionResults: {},
    response: { clientDataJSON: b64url(r.clientDataJSON), authenticatorData: b64url(r.authenticatorData), signature: b64url(r.signature), userHandle: r.userHandle ? b64url(r.userHandle) : null } };
  return { key_id: key.id, challenge: ch.challenge, assertion };
}
