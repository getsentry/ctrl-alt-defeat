"""
Shop generation logic - wrapper to avoid circular imports
"""


def generate_shop_items(round_number, seed=None):
    """Generate shop items - deferred import to avoid circular dependency"""
    from main import generate_shop_items as _generate_shop

    return _generate_shop(round_number, seed)
