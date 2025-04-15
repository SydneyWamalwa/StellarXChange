pub fn calculate_fee(_env: Env, tx_count: u32, amount: u32) -> u32 {
    // Base fee component (very small fixed cost)
    let base_fee = 5;

    // Variable fee based on transaction amount (0.1% = 1/1000)
    let variable_fee = amount / 1000;

    // Volume discount for higher tx_count
    let volume_multiplier = if tx_count > 100 {
        80  // 20% discount for high volume
    } else if tx_count > 10 {
        90  // 10% discount for medium volume
    } else {
        100 // No discount for low volume
    };

    // Calculate total fee with volume discount applied
    base_fee + (variable_fee * volume_multiplier / 100)
}