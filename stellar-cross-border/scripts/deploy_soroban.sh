#!/bin/bash
set -e

cd contracts/fee_adjustment
cargo build --target wasm32-unknown-unknown --release
echo "Contract built successfully. Output: target/wasm32-unknown-unknown/release/fee_adjustment.wasm"
