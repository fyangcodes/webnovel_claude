def breadcrumb_context(request):
    """
    Context processor to provide default values for breadcrumb variables
    to prevent VariableDoesNotExist errors in templates.

    All breadcrumb-related variables default to None and can be overridden
    by view contexts as needed.
    """
    return {
        "bookmaster": None,
        "book": None,
        "chaptermaster": None,
        "chapter": None,
    }
