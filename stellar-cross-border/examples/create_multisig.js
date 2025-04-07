import { createMultisigAccount } from '../src/account_service.js';

const signers = [
  { publicKey: 'GABC123...', weight: 1 },
  { publicKey: 'GDEF456...', weight: 1 },
  { publicKey: 'GHIJ789...', weight: 1 }
];

const thresholds = { low: 2, med: 2, high: 2 };

async function main() {
  const result = await createMultisigAccount(signers, thresholds);
  console.log('Created account:', result);
}

main().catch(console.error);
