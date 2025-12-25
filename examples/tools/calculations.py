"""
Example calculation tools for Tactus demonstrations.

These demonstrate type-safe mathematical operations as tools.
"""


def calculate_mortgage(principal: float, annual_rate: float, years: int) -> str:
    """
    Calculate monthly mortgage payment.

    Args:
        principal: Loan amount in dollars
        annual_rate: Annual interest rate (as percentage, e.g., 5.5 for 5.5%)
        years: Loan term in years

    Returns:
        Formatted string with payment details
    """
    monthly_rate = annual_rate / 100 / 12
    num_payments = years * 12

    if monthly_rate == 0:
        # No interest case
        monthly_payment = principal / num_payments
    else:
        monthly_payment = (
            principal
            * (monthly_rate * (1 + monthly_rate) ** num_payments)
            / ((1 + monthly_rate) ** num_payments - 1)
        )

    total_paid = monthly_payment * num_payments
    total_interest = total_paid - principal

    return f"""Mortgage Calculation Results:
- Loan Amount: ${principal:,.2f}
- Interest Rate: {annual_rate}% per year
- Loan Term: {years} years
- Monthly Payment: ${monthly_payment:,.2f}
- Total Amount Paid: ${total_paid:,.2f}
- Total Interest: ${total_interest:,.2f}
"""


def compound_interest(
    principal: float, annual_rate: float, years: int, compounds_per_year: int = 12
) -> str:
    """
    Calculate compound interest.

    Args:
        principal: Initial investment amount
        annual_rate: Annual interest rate (as percentage)
        years: Investment period in years
        compounds_per_year: Number of times interest compounds per year (default: 12 for monthly)

    Returns:
        Formatted string with investment growth details
    """
    rate_decimal = annual_rate / 100
    final_amount = principal * (1 + rate_decimal / compounds_per_year) ** (
        compounds_per_year * years
    )
    interest_earned = final_amount - principal

    return f"""Compound Interest Calculation:
- Initial Investment: ${principal:,.2f}
- Annual Rate: {annual_rate}%
- Time Period: {years} years
- Compounding: {compounds_per_year} times per year
- Final Amount: ${final_amount:,.2f}
- Interest Earned: ${interest_earned:,.2f}
- Total Return: {(interest_earned / principal * 100):.2f}%
"""


def tip_calculator(bill_amount: float, tip_percentage: float, split_ways: int = 1) -> str:
    """
    Calculate tip and split bill.

    Args:
        bill_amount: Total bill amount
        tip_percentage: Tip percentage (e.g., 18 for 18%)
        split_ways: Number of people to split the bill (default: 1)

    Returns:
        Formatted string with tip and split details
    """
    tip_amount = bill_amount * (tip_percentage / 100)
    total_with_tip = bill_amount + tip_amount
    per_person = total_with_tip / split_ways

    result = f"""Tip Calculation:
- Bill Amount: ${bill_amount:.2f}
- Tip ({tip_percentage}%): ${tip_amount:.2f}
- Total with Tip: ${total_with_tip:.2f}
"""

    if split_ways > 1:
        result += f"- Split {split_ways} ways: ${per_person:.2f} per person"

    return result
