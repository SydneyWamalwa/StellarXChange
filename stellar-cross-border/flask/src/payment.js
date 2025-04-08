#!/usr/bin/env node
// src/payment.js
import * as StellarSdk from 'stellar-sdk';
import { config } from '../config/networks.js';

const server = new StellarSdk.Horizon.Server(config.testnet.horizonUrl);

// Parse command-line arguments into a key/value object
const args = process.argv.slice(2).reduce((acc, arg) => {
  const [key, value] = arg.split('=');
  acc[key.replace('--', '')] = value;
  return acc;
}, {});

// Validate required arguments
if (!args.source || !args.dest || !args.amount) {
  console.error('Missing required arguments: --source, --dest, or --amount');
  process.exit(1);
}

async function executePayment() {
  try {
    const sourceKey = StellarSdk.Keypair.fromSecret(args.source);
    console.log('Source Public:', sourceKey.publicKey());

    // Verify destination account exists
    console.log('Verifying destination account...');
    await server.loadAccount(args.dest);

    console.log('Using network:', config.testnet.horizonUrl);
    const sourceAccount = await server.loadAccount(sourceKey.publicKey());

    // Build the payment transaction
    const transaction = new StellarSdk.TransactionBuilder(sourceAccount, {
      fee: StellarSdk.BASE_FEE,
      networkPassphrase: config.testnet.networkPassphrase
    })
      .addOperation(StellarSdk.Operation.payment({
        destination: args.dest,
        asset: StellarSdk.Asset.native(),
        amount: args.amount.toString()
      }))
      .setTimeout(30)
      .build();

    transaction.sign(sourceKey);
    const result = await server.submitTransaction(transaction);
    console.log('Payment successful. Transaction hash:', result.hash);
  } catch (error) {
    console.error('Payment failed:', error.response?.data || error.message);
  }
}

executePayment();