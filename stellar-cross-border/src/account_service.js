import StellarSdk from 'stellar-sdk';
import { config } from '../config/networks.js';
import fetch from 'node-fetch';
globalThis.fetch = fetch; // Polyfill for Node.js

export async function createMultisigAccount(signers, thresholds) {
  const server = new StellarSdk.Server(config.horizonUrl);
  const masterKey = StellarSdk.Keypair.random();

  // Fund master account via Friendbot (Testnet only)
  await fetch(`${config.friendbotUrl}?addr=${masterKey.publicKey()}`);

  const account = await server.loadAccount(masterKey.publicKey());
  const tx = new StellarSdk.TransactionBuilder(account, {
    networkPassphrase: config.networkPassphrase,
    fee: StellarSdk.BASE_FEE
  })
    .addOperation(StellarSdk.Operation.setOptions({
      masterWeight: 0,
      signer: signers.map(s => ({
        ed25519PublicKey: s.publicKey,
        weight: s.weight
      })),
      thresholds: {
        low: thresholds.low,
        med: thresholds.med,
        high: thresholds.high
      }
    }))
    .setTimeout(30)
    .build();

  tx.sign(masterKey);
  return server.submitTransaction(tx);
}
