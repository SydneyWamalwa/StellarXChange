// examples/create_multisig.js
import { createMultisigAccount } from '../src/account_service.js';
import * as StellarSdk from 'stellar-sdk';

// Generate real keypairs for the signers
const keypair1 = StellarSdk.Keypair.random();
const keypair2 = StellarSdk.Keypair.random();
const keypair3 = StellarSdk.Keypair.random();

const signers = [
  { publicKey: keypair1.publicKey(), weight: 1 },
  { publicKey: keypair2.publicKey(), weight: 1 },
  { publicKey: keypair3.publicKey(), weight: 1 }
];

// Log keys for future reference
console.log('Generated keypairs:');
console.log(`Keypair 1 - Public: ${keypair1.publicKey()}, Secret: ${keypair1.secret()}`);
console.log(`Keypair 2 - Public: ${keypair2.publicKey()}, Secret: ${keypair2.secret()}`);
console.log(`Keypair 3 - Public: ${keypair3.publicKey()}, Secret: ${keypair3.secret()}`);

const thresholds = { low: 2, med: 2, high: 2 };

async function main() {
  try {
    const result = await createMultisigAccount(signers, thresholds);
    console.log('Created multisig account:', result.id);
    console.log('Transaction successful:', result._links.transaction.href);
  } catch (error) {
    console.error('Error creating multisig account:', error);
  }
}

main().catch(console.error);