def breadcrumb_context(request):
    """
    Context processor to provide default values for breadcrumb variables
    to prevent VariableDoesNotExist errors in templates.
    """
    return {
        "bookmaster": None,
        "book": None,
        "chaptermaster": None,
        "chapter": None
    }
