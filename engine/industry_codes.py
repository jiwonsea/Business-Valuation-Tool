"""Pure classification of the explicitly supported SIC and KSIC systems."""

SIC_FINANCIAL_RANGE = (6000, 6799)
KSIC_FINANCIAL_PREFIXES = ("64", "65", "66")


def is_financial_code(code: str | None) -> bool | None:
    """Return None for missing, unsupported or malformed industry codes."""
    if not code:
        return None
    system, separator, value = code.partition(":")
    if not separator or not value.isdigit():
        return None
    if system == "SIC":
        return SIC_FINANCIAL_RANGE[0] <= int(value) <= SIC_FINANCIAL_RANGE[1]
    if system == "KSIC":
        return value.startswith(KSIC_FINANCIAL_PREFIXES)
    return None
