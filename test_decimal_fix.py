"""
Simple test to verify decimal calculations for TRX
"""
print("Testing TRX decimal calculations...")

# Simulate a TRX balance check
# Let's say we get a raw balance of 1000000 (1 TRX with 6 decimals)
raw_balance = 1000000

# Old method (WRONG - uses 18 decimals)
old_method = raw_balance / (10 ** 18)
print(f"Old method (18 decimals): {old_method:.18f}")

# New method (CORRECT - uses 6 decimals for TRX)
new_method = raw_balance / (10 ** 6)
print(f"New method (6 decimals): {new_method:.8f}")

print("\nComparison:")
print(f"Raw balance: {raw_balance}")
print(f"Old method result: {old_method}")
print(f"New method result: {new_method}")

print("\nThe difference is HUGE!")
print(f"New method is {new_method / old_method:.0f}x larger than old method")

print("\nThis explains why TRX balances were showing as essentially 0!")
