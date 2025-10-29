# Reader Tailwind Templates

This directory contains templates using the Tailwind CSS framework for the reader app.

## Base Template

**File:** `reader-tw/base.html`

The base template provides the common layout structure including:
- Navigation bar with logo, genres dropdown, language switcher, and theme toggle
- Footer
- Bootstrap integration
- Font Awesome icons
- Tailwind CSS styles

### Context Variables Required

The base template expects the following context variables:

- `current_language` - Language object (provides code, name, local_name)
- `languages` - QuerySet of all Language objects (for language switcher)
- `genres` - List of Genre objects with `localized_name` attribute (for genres dropdown)
- `user` - User object (automatically provided by Django)

## Using BaseTailwindView

To create a new view that uses the `reader-tw/base.html` template:

### 1. Import the base view class

```python
from reader.views import BaseTailwindView
```

### 2. Create your view class

```python
class MyCustomView(BaseTailwindView):
    """Your custom view description"""
    template_name = "reader-tw/my_template.html"

    def get_context_data(self, **kwargs):
        # Get base context (current_language, languages, genres)
        context = super().get_context_data(**kwargs)

        # Add your custom context
        context["my_data"] = "custom data"

        return context
```

### 3. Create your template

```html
{% extends "reader-tw/base.html" %}

{% block title %}My Page Title{% endblock %}

{% block content %}
<div class="container">
    <h1>My Content</h1>
    <p>{{ my_data }}</p>
</div>
{% endblock %}
```

### 4. Add URL pattern

```python
from reader.views import MyCustomView

urlpatterns = [
    path(
        "<str:language_code>/my-page/",
        MyCustomView.as_view(),
        name="my_page",
    ),
]
```

## Example

See `TailwindExampleView` in [reader/views.py](../../views.py:44) and the template [reader-tw/example.html](example.html) for a working example.

To view the example:
- Run the Django development server
- Navigate to `http://127.0.0.1:8000/en/example/` (replace `en` with any available language code)

## Available Template Blocks

- `{% block title %}` - Page title (appended with " - wereadly")
- `{% block extra_css %}` - Additional CSS files or styles
- `{% block breadcrumb_section %}` - Custom breadcrumb navigation
- `{% block content %}` - Main page content
- `{% block extra_js %}` - Additional JavaScript files or scripts
