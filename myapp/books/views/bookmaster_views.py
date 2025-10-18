from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    CreateView,
    ListView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.core.paginator import Paginator

from books.models import BookMaster, Language
from books.forms import BookMasterForm


class BookMasterCreateView(LoginRequiredMixin, CreateView):
    model = BookMaster
    form_class = BookMasterForm
    template_name = "books/bookmaster/form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "books_admin:bookmaster_detail", kwargs={"pk": self.object.pk}
        )


class BookMasterListView(LoginRequiredMixin, ListView):
    model = BookMaster
    template_name = "books/bookmaster/list.html"
    context_object_name = "bookmasters"

    def get_queryset(self):
        return BookMaster.objects.filter(owner=self.request.user).prefetch_related(
            "chaptermasters",
            "books__language",
            "book_genres__genre"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add extra information for each bookmaster
        bookmasters_with_info = []
        for bookmaster in context["bookmasters"]:
            chapter_count = bookmaster.chaptermasters.count()
            languages = list(
                bookmaster.books.values_list("language__name", flat=True).distinct()
            )
            language_count = len(languages)
            # Get genres in order
            genres = [
                bg.genre for bg in bookmaster.book_genres.all()
            ]

            bookmasters_with_info.append(
                {
                    "bookmaster": bookmaster,
                    "chapter_count": chapter_count,
                    "language_count": language_count,
                    "languages": languages,
                    "genres": genres,
                }
            )

        context["bookmasters_with_info"] = bookmasters_with_info
        return context


class BookMasterDetailView(LoginRequiredMixin, DetailView):
    model = BookMaster
    template_name = "books/bookmaster/detail.html"
    context_object_name = "bookmaster"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["books"] = self.object.books.all().order_by("language__name")

        # Get all chaptermasters ordered by chapter number
        chaptermasters_queryset = self.object.chaptermasters.all().order_by(
            "chapter_number"
        )

        # Add pagination
        paginator = Paginator(chaptermasters_queryset, 20)
        page_number = self.request.GET.get("page")
        chaptermasters_page = paginator.get_page(page_number)

        context["chaptermasters"] = chaptermasters_page

        # Create chapter status table data for the current page
        languages = [book.language for book in context["books"]]
        chapter_table = []

        for chaptermaster in chaptermasters_page:
            row = {"chaptermaster": chaptermaster, "chapters": {}}

            # Get chapters for this chapter master in each language
            for language in languages:
                try:
                    chapter = chaptermaster.chapters.get(book__language=language)
                    row["chapters"][language.code] = {
                        "chapter": chapter,
                        "status": chapter.get_progress_display(),
                        "status_code": chapter.progress,
                        "is_public": chapter.is_public,
                        "url": (
                            chapter.get_absolute_url()
                            if hasattr(chapter, "get_absolute_url")
                            else None
                        ),
                    }
                except:
                    row["chapters"][language.code] = {
                        "chapter": None,
                        "status": "Not Created",
                        "status_code": "none",
                        "is_public": False,
                        "url": None,
                    }

            chapter_table.append(row)

        context["languages"] = languages
        context["chapter_table"] = chapter_table

        # Add all available languages for translation modal
        context["all_languages"] = Language.objects.all().order_by("name")

        return context


class BookMasterUpdateView(LoginRequiredMixin, UpdateView):
    model = BookMaster
    form_class = BookMasterForm
    template_name = "books/bookmaster/form.html"
    context_object_name = "bookmaster"

    def get_success_url(self):
        return reverse_lazy(
            "books_admin:bookmaster_detail", kwargs={"pk": self.object.pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object
        return context


class BookMasterDeleteView(LoginRequiredMixin, DeleteView):
    model = BookMaster
    template_name = "books/bookmaster/confirm_delete.html"
    context_object_name = "bookmaster"
    success_url = reverse_lazy("books_admin:bookmaster_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object
        return context
