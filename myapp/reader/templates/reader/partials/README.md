# Reader Partials

This directory contains reusable template partials for the reader app.

## Rotating Carousel

A 3D rotating carousel component for displaying books with a centered highlight and scaled side books.

### Files

**Template:**
- `rotating_carousel.html` - Main HTML structure (in this directory)

**Static Assets:**
- `static/reader/css/rotating_carousel.css` - Carousel styles
- `static/reader/js/rotating_carousel.js` - Carousel JavaScript functionality

### Usage

```django
{% load static %}

{% block extra_css %}
<link href="{% static 'reader/css/rotating_carousel.css' %}" rel="stylesheet">
{% endblock %}

{% block content %}
<!-- Your content -->
{% include "reader/partials/rotating_carousel.html" with books=featured_books section_id="featured" %}
{% endblock %}

{% block extra_js %}
<script src="{% static 'reader/js/rotating_carousel.js' %}"></script>
{% endblock %}
```

### Parameters

- **books** (required): QuerySet of Book objects to display
- **section_id** (required): Unique identifier for this carousel instance (e.g., "featured", "popular")
- **current_language** (optional): Language object (defaults to context variable)

### Features

- **Auto-rotation**: Automatically rotates every 5 seconds
- **Navigation buttons**: Previous/Next buttons on sides
- **Click navigation**: Click side books to bring them to center
- **Keyboard support**: Arrow keys (left/right)
- **Touch/swipe**: Swipe gestures for mobile
- **Pause on hover**: Auto-rotation pauses on hover
- **Indicators**: Dot indicators showing current position
- **Responsive**: Adapts to different screen sizes

### Book Object Requirements

The books queryset should include books with:
- `effective_cover_image` - Cover image URL
- `title` - Book title
- `slug` - URL slug
- `description` - Book description (optional)
- `published_chapters_count` - Number of chapters (added via view)
- `reading_time_minutes` - Reading time (from Book model property)
- `bookmaster.genres.all()` - Related genres with `localized_name` attribute

### Multiple Carousels

You can have multiple carousels on the same page by using different `section_id` values:

```django
{% include "reader/partials/rotating_carousel.html" with books=featured_books section_id="featured" %}
{% include "reader/partials/rotating_carousel.html" with books=popular_books section_id="popular" %}
```

The JavaScript automatically initializes all carousels on the page.
