# HTMX Pagination Guide

This guide explains how to add HTMX-based Ajax pagination to the chapter list.

## Current Architecture

The chapter list has been refactored into a reusable partial:

- **Template**: `reader/templates/reader/partials/chapter_list.html`
- **Container**: `#chapter-list-container` in `book_detail.html`
- **View**: `SectionBookDetailView.get_context_data()` in `reader/views/section_views.py`

## Steps to Enable HTMX Pagination

### 1. Install HTMX

Add HTMX to your base template:

```html
<!-- In reader/templates/reader/base.html, add to head section -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
```

### 2. Create a Partial-Only View

Add a new view that returns only the chapter list partial (without the full page):

```python
# In reader/views/section_views.py

class SectionBookChapterListPartialView(BaseReaderView, DetailView):
    """
    Returns only the chapter list partial for HTMX requests.

    URL: /<language>/<section>/book/<slug>/chapters/
    Query params: ?page=N
    """
    template_name = "reader/partials/chapter_list.html"
    model = Book
    context_object_name = "book"

    def get_queryset(self):
        language = self.get_language()
        section = self.get_section()

        if not section:
            raise Http404("Section required")

        return Book.objects.filter(
            language=language,
            is_public=True,
            bookmaster__section=section
        ).select_related("bookmaster__section", "language")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all published chapters
        all_chapters = (
            self.object.chapters.filter(is_public=True)
            .select_related("chaptermaster")
            .order_by("chaptermaster__chapter_number")
        )

        # Pagination
        paginator = Paginator(all_chapters, 2)  # Match main view
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["chapters"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["page_obj"] = page_obj
        context["current_language"] = self.get_language()

        return context
```

### 3. Add URL Route

```python
# In reader/urls.py

urlpatterns = [
    # ... existing patterns ...

    # Chapter list partial for HTMX
    path(
        "<str:language_code>/<slug:section_slug>/book/<uslug:book_slug>/chapters/",
        views.SectionBookChapterListPartialView.as_view(),
        name="section_book_chapters_partial",
    ),
]
```

### 4. Update the Partial Template

Uncomment the HTMX attributes in `reader/templates/reader/partials/chapter_list.html`:

```html
<!-- Replace this: -->
<a href="?page=1" class="btn btn-outline-secondary btn-sm">1</a>

<!-- With this: -->
<a href="?page=1"
   class="btn btn-outline-secondary btn-sm"
   hx-get="{% url 'reader:section_book_chapters_partial' current_language.code book.bookmaster.section.slug book.slug %}?page=1"
   hx-target="#chapter-list-container"
   hx-swap="outerHTML">
    1
</a>
```

Apply this pattern to all pagination links.

### 5. Add Loading Indicator (Optional)

```html
<!-- In reader/templates/reader/book_detail.html -->
<div id="chapter-list-container" class="htmx-indicator">
    {% include "reader/partials/chapter_list.html" %}
</div>

<!-- Add CSS for loading state -->
<style>
.htmx-indicator.htmx-request {
    opacity: 0.5;
    pointer-events: none;
}
</style>
```

### 6. Add Scroll to Top (Optional)

```html
<!-- Update pagination links to scroll to top -->
<a href="?page=1"
   hx-get="..."
   hx-target="#chapter-list-container"
   hx-swap="outerHTML"
   hx-on::after-request="window.scrollTo({top: document.getElementById('chapter-list-container').offsetTop - 100, behavior: 'smooth'})">
    1
</a>
```

## Benefits of This Architecture

1. **Progressive Enhancement**: Works with JavaScript disabled (falls back to normal pagination)
2. **No Page Reloads**: Faster, smoother user experience
3. **SEO Friendly**: URLs with `?page=N` are still crawlable
4. **Easy to Test**: Partial view can be tested independently
5. **Reusable**: Same partial works for both full page and HTMX requests

## Testing

1. Test without HTMX (should work with normal page loads)
2. Test with HTMX enabled (should load chapters via Ajax)
3. Test browser back/forward buttons (HTMX supports history)
4. Test with network throttling (loading indicators should show)

## Current Status

✅ Chapter list extracted to partial template
✅ Container div with ID for HTMX targeting
✅ Pagination logic in separate partial
✅ HTMX attributes commented in template (ready to uncomment)
⏸️ HTMX script not yet included
⏸️ Partial-only view not yet created
⏸️ URL route not yet added

To enable HTMX pagination, follow steps 1-6 above.
