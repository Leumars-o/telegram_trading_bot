"""
Example script demonstrating Jupiter Swap usage
"""

import os
from jupiter_swap import JupiterSwap, TOKENS, sol_to_lamports
from dotenv import load_dotenv

load_dotenv()


def example_sol_to_usdc():
    """Example: Swap 0.1 SOL to USDC"""
    print("Example: Swapping 0.1 SOL to USDC")
    print("=" * 60)

    # Get private key from environment variable (recommended)
    private_key = os.getenv('SOLANA_PRIVATE_KEY')

    if not private_key:
        print("Error: SOLANA_PRIVATE_KEY not set in .env file")
        print("Add this line to your .env file:")
        print("SOLANA_PRIVATE_KEY=your_private_key_here")
        return

    # Initialize swap handler
    swap_handler = JupiterSwap(private_key)

    # Execute swap
    success = swap_handler.swap(
        input_mint=TOKENS['SOL'],
        output_mint=TOKENS['USDC'],
        amount=sol_to_lamports(0.1),  # 0.1 SOL
        slippage_bps=50,  # 0.5% slippage
        simulate=True  # Change to False to execute real swap
    )

    if success:
        print("\nSwap completed successfully!")
    else:
        print("\nSwap failed!")


def example_get_quote_only():
    """Example: Get quote without executing swap"""
    print("\nExample: Getting quote for SOL to BONK")
    print("=" * 60)

    private_key = os.getenv('SOLANA_PRIVATE_KEY')

    if not private_key:
        print("Error: SOLANA_PRIVATE_KEY not set in .env file")
        return

    swap_handler = JupiterSwap(private_key)

    # Get quote
    quote = swap_handler.get_quote(
        input_mint=TOKENS['SOL'],
        output_mint=TOKENS['BONK'],
        amount=sol_to_lamports(0.1),
        slippage_bps=50
    )

    if quote:
        in_amount = int(quote['inAmount']) / 1e9
        out_amount = int(quote['outAmount'])
        price_impact = float(quote.get('priceImpactPct', 0))

        print(f"\nQuote received:")
        print(f"  Input: {in_amount} SOL")
        print(f"  Output: {out_amount:,.0f} BONK")
        print(f"  Price Impact: {price_impact:.4f}%")
        print(f"  Rate: 1 SOL = {out_amount/in_amount:,.0f} BONK")
    else:
        print("Failed to get quote")


def example_custom_token():
    """Example: Swap to a custom token address"""
    print("\nExample: Swapping to custom token")
    print("=" * 60)

    private_key = os.getenv('SOLANA_PRIVATE_KEY')

    if not private_key:
        print("Error: SOLANA_PRIVATE_KEY not set in .env file")
        return

    # Example: Swap SOL to JUP token
    custom_token_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"

    swap_handler = JupiterSwap(private_key)

    success = swap_handler.swap(
        input_mint=TOKENS['SOL'],
        output_mint=custom_token_mint,
        amount=sol_to_lamports(0.05),  # 0.05 SOL
        slippage_bps=100,  # 1% slippage
        simulate=True  # Change to False to execute
    )

    if success:
        print("\nSwap completed!")


def example_multiple_quotes():
    """Example: Compare quotes for multiple tokens"""
    print("\nExample: Comparing quotes for multiple tokens")
    print("=" * 60)

    private_key = os.getenv('SOLANA_PRIVATE_KEY')

    if not private_key:
        print("Error: SOLANA_PRIVATE_KEY not set in .env file")
        return

    swap_handler = JupiterSwap(private_key)
    sol_amount = 1.0  # 1 SOL

    # Tokens to compare
    compare_tokens = ['USDC', 'USDT', 'BONK', 'JUP']

    print(f"\nComparing quotes for {sol_amount} SOL:\n")

    for token_symbol in compare_tokens:
        if token_symbol not in TOKENS:
            continue

        quote = swap_handler.get_quote(
            input_mint=TOKENS['SOL'],
            output_mint=TOKENS[token_symbol],
            amount=sol_to_lamports(sol_amount),
            slippage_bps=50
        )

        if quote:
            out_amount = int(quote['outAmount'])
            # Adjust decimals based on token (most use 6, BONK uses 5)
            decimals = 6
            if token_symbol == 'BONK':
                decimals = 5

            formatted_amount = out_amount / (10 ** decimals)
            price_impact = float(quote.get('priceImpactPct', 0))

            print(f"  {token_symbol:6s}: {formatted_amount:>15,.2f}  (Impact: {price_impact:.4f}%)")


if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print("Jupiter Swap Examples")
    print("=" * 60)
    print("\nNote: These examples use SIMULATE mode by default.")
    print("Change simulate=True to simulate=False to execute real swaps.")
    print("=" * 60)

    # Run examples
    example_sol_to_usdc()
    print("\n")

    example_get_quote_only()
    print("\n")

    example_custom_token()
    print("\n")

    example_multiple_quotes()
    print("\n")

    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)
