// src/account_service.js - Updated version
import * as StellarSdk from 'stellar-sdk';
import { config } from '../config/networks.js';
import fetch from 'node-fetch';

// Polyfill fetch for Node.js
globalThis.fetch = fetch;

export async function createMultisigAccount(signers, thresholds) {
  const server = new StellarSdk.Horizon.Server(config.testnet.horizonUrl);
  const masterKey = StellarSdk.Keypair.random();

  // Fund master account using Friendbot on Testnet
  await fetch(`${config.testnet.friendbotUrl}?addr=${masterKey.publicKey()}`);

  // Load the freshly funded account
  const account = await server.loadAccount(masterKey.publicKey());

  // Start transaction builder
  const txBuilder = new StellarSdk.TransactionBuilder(account, {
    networkPassphrase: config.testnet.networkPassphrase,
    fee: StellarSdk.BASE_FEE
  });

  // First set masterWeight to 0
  txBuilder.addOperation(StellarSdk.Operation.setOptions({
    masterWeight: 0, // Disable single-party control
    lowThreshold: thresholds.low,
    medThreshold: thresholds.med,
    highThreshold: thresholds.high
  }));

  // Add each signer as a separate operation
  for (const signer of signers) {
    txBuilder.addOperation(StellarSdk.Operation.setOptions({
      signer: {
        ed25519PublicKey: signer.publicKey,
        weight: signer.weight
      }
    }));
  }

  const tx = txBuilder.setTimeout(30).build();
  tx.sign(masterKey);
  return server.submitTransaction(tx);
}