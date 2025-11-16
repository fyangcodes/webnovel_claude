"""
Robots.txt view for SEO.
"""

from django.http import HttpResponse
from django.views import View


class RobotsTxtView(View):
    """
    Generate robots.txt dynamically.

    Provides:
    - Sitemap location
    - Crawl rules
    - Allow/disallow paths
    """

    def get(self, request):
        """Generate robots.txt content"""
        sitemap_url = request.build_absolute_uri('/sitemap.xml')

        lines = [
            "User-agent: *",
            "Allow: /",
            "",
            "# Sitemaps",
            f"Sitemap: {sitemap_url}",
            "",
            "# Disallow admin and private areas",
            "Disallow: /admin/",
            "Disallow: /staff/",
            "Disallow: /accounts/",
            "",
            "# Crawl-delay (optional, adjust as needed)",
            "Crawl-delay: 1",
        ]

        return HttpResponse("\n".join(lines), content_type="text/plain")
