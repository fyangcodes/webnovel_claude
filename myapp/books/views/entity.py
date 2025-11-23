from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, UpdateView, DeleteView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.urls import reverse_lazy
from django.contrib import messages

from books.models import BookMaster, BookEntity
from books.choices import EntityType


class BookEntityListView(LoginRequiredMixin, ListView):
    model = BookEntity
    template_name = "books/entity/list.html"
    context_object_name = "entities"
    paginate_by = 50

    def get_queryset(self):
        self.bookmaster = get_object_or_404(
            BookMaster, pk=self.kwargs["bookmaster_pk"], owner=self.request.user
        )

        queryset = BookEntity.objects.filter(bookmaster=self.bookmaster).select_related(
            "first_chapter__chaptermaster",
            "first_chapter__book",
            "first_chapter__book__language",
            "last_chapter__chaptermaster",
        )

        # Filter by entity type
        entity_type = self.request.GET.get("type", "").lower()
        if entity_type in [EntityType.CHARACTER, EntityType.PLACE, EntityType.TERM]:
            queryset = queryset.filter(entity_type=entity_type)

        # Search by entity name
        search = self.request.GET.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(source_name__icontains=search)
                | Q(translations__icontains=search)
            )

        # Order by priority (order field), then first appearance, then name
        queryset = queryset.order_by(
            "order",
            "first_chapter__chaptermaster__chapter_number",
            "source_name"
        )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.bookmaster

        # Get books with languages
        books = self.bookmaster.books.select_related("language").order_by(
            "language__name"
        )
        context["books"] = books

        # Get languages, filtering out None values and original language
        # (translations in original language are redundant)
        original_lang_code = self.bookmaster.original_language.code if self.bookmaster.original_language else None
        context["languages"] = [
            book.language for book in books
            if book.language and book.language.code != original_lang_code
        ]

        # Add filter state
        context["current_type"] = self.request.GET.get("type", "").lower()
        context["search_query"] = self.request.GET.get("search", "")

        # Add entity counts by type
        all_entities = BookEntity.objects.filter(bookmaster=self.bookmaster)
        context["entity_counts"] = {
            "all": all_entities.count(),
            "character": all_entities.filter(entity_type=EntityType.CHARACTER).count(),
            "place": all_entities.filter(entity_type=EntityType.PLACE).count(),
            "term": all_entities.filter(entity_type=EntityType.TERM).count(),
        }

        return context


class BookEntityUpdateView(LoginRequiredMixin, UpdateView):
    model = BookEntity
    template_name = "books/entity/update.html"
    fields = ["entity_type", "source_name", "order", "translations"]
    context_object_name = "entity"

    def get_queryset(self):
        """Ensure user can only edit entities from their own bookmasters"""
        return BookEntity.objects.filter(bookmaster__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object.bookmaster
        return context

    def get_success_url(self):
        messages.success(self.request, f"Entity '{self.object.source_name}' updated successfully.")
        return reverse_lazy(
            "books:bookmaster_entities", kwargs={"bookmaster_pk": self.object.bookmaster.pk}
        )


class BookEntityDeleteView(LoginRequiredMixin, DeleteView):
    model = BookEntity
    template_name = "books/entity/delete.html"
    context_object_name = "entity"

    def get_queryset(self):
        """Ensure user can only delete entities from their own bookmasters"""
        return BookEntity.objects.filter(bookmaster__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object.bookmaster
        return context

    def get_success_url(self):
        bookmaster_pk = self.object.bookmaster.pk
        messages.success(self.request, f"Entity '{self.object.source_name}' deleted successfully.")
        return reverse_lazy("books:bookmaster_entities", kwargs={"bookmaster_pk": bookmaster_pk})
