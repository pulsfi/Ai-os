"use client";

/**
 * Minimal Phantom wallet bridge — non-custodial by construction.
 *
 * The app never sees a private key. It hands Phantom an UNSIGNED
 * transaction (built server-side via Jupiter); Phantom asks the user to
 * approve, signs locally, and submits. We only ever get back a public
 * key and a transaction signature.
 */
import { VersionedTransaction } from "@solana/web3.js";

interface PhantomProvider {
  isPhantom?: boolean;
  publicKey?: { toString(): string } | null;
  connect(opts?: { onlyIfTrusted?: boolean }): Promise<{ publicKey: { toString(): string } }>;
  disconnect(): Promise<void>;
  signAndSendTransaction(tx: VersionedTransaction): Promise<{ signature: string }>;
}

function getProvider(): PhantomProvider | null {
  if (typeof window === "undefined") return null;
  const anyWindow = window as unknown as { solana?: PhantomProvider; phantom?: { solana?: PhantomProvider } };
  const provider = anyWindow.phantom?.solana ?? anyWindow.solana;
  return provider?.isPhantom ? provider : null;
}

export const phantom = {
  installed(): boolean {
    return getProvider() !== null;
  },

  async connect(): Promise<string> {
    const provider = getProvider();
    if (!provider) throw new Error("Phantom wallet not found. Install it at phantom.app.");
    const { publicKey } = await provider.connect();
    return publicKey.toString();
  },

  async disconnect(): Promise<void> {
    await getProvider()?.disconnect();
  },

  /** Deserialize the server-built swap, have Phantom sign+send it. */
  async signAndSend(swapTransactionB64: string): Promise<string> {
    const provider = getProvider();
    if (!provider) throw new Error("Phantom wallet not found.");
    const bytes = Uint8Array.from(atob(swapTransactionB64), (c) => c.charCodeAt(0));
    const tx = VersionedTransaction.deserialize(bytes);
    const { signature } = await provider.signAndSendTransaction(tx);
    return signature;
  },
};
