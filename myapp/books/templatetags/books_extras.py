from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter(name="markdown")
def markdown_format(text):
    """Simple markdown replacement for MVP - just convert newlines to <br>"""
    return mark_safe(text.replace("\n", "<br>"))


@register.filter
def exists(value):
    """Check if a variable exists and is not None"""
    return value is not None


@register.filter
def natural_count(value, language_code="en"):
    """
    Format numbers in a natural way based on language settings.
    Uses the count_format_rules from the Language model.

    Example rules:
    - English: {"6": "M", "3": "K"} -> 100000 -> 100K, 1000000 -> 1M
    - Chinese: {"8": "亿", "4": "万"} -> 100000 -> 10万, 1000000 -> 100万
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return value

    if num < 1000:
        return str(int(num))

    # Try to get language formatting rules from database
    from books.models import Language

    try:
        language = Language.objects.get(code=language_code)
        rules = language.count_format_rules

        if rules:
            # Convert string keys to integers and sort by power (descending)
            sorted_rules = sorted(
                [(int(k), v) for k, v in rules.items()],
                key=lambda x: x[0],
                reverse=True,
            )

            # Apply the first matching rule
            for power, suffix in sorted_rules:
                threshold = 10**power
                if num >= threshold:
                    formatted_value = num / threshold
                    # Show decimal for small values, integer for large
                    if formatted_value < 10:
                        result = f"{formatted_value:.1f}{suffix}"
                    else:
                        result = f"{formatted_value:.0f}{suffix}"
                    # Remove trailing .0
                    return result.replace(".0" + suffix, suffix)

    except Language.DoesNotExist:
        pass

    # Fallback: return the number as-is if no formatting rules matched
    return str(int(num))
