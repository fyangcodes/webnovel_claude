from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db import transaction, IntegrityError
from django.contrib import messages

from books.models import ChapterMaster, Chapter, Language
from books.forms import ChapterMasterForm


class ChapterMasterCreateView(LoginRequiredMixin, CreateView):
    model = ChapterMaster
    form_class = ChapterMasterForm
    template_name = "books/chaptermaster/form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Chapter {self.object.chapter_number} '{self.object.canonical_title}' created successfully."
        )
        return response

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.id}
        )


class ChapterMasterDetailView(LoginRequiredMixin, DetailView):
    model = ChapterMaster
    template_name = "books/chaptermaster/detail.html"
    context_object_name = "chaptermaster"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapters = Chapter.objects.filter(chaptermaster=self.object)
        context["chapters"] = chapters
        context["available_languages"] = Language.objects.exclude(
            id__in=chapters.values_list("book__language_id", flat=True)
        )
        context["chapter_original"] = chapters.filter(
            book__language=self.object.bookmaster.original_language
        ).first()
        context["bookmaster"] = self.object.bookmaster
        return context


class ChapterMasterUpdateView(LoginRequiredMixin, UpdateView):
    model = ChapterMaster
    form_class = ChapterMasterForm
    template_name = "books/chaptermaster/form.html"

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.id}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object.bookmaster
        return context


class ChapterMasterDeleteView(LoginRequiredMixin, DeleteView):
    model = ChapterMaster
    template_name = "books/chaptermaster/confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.id}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmaster"] = self.object.bookmaster
        return context

    @transaction.atomic
    def form_valid(self, form):
        chaptermaster = self.get_object()
        bookmaster = chaptermaster.bookmaster
        deleted_chapter_number = chaptermaster.chapter_number
        deleted_chapter_title = chaptermaster.canonical_title

        try:
            # Get all chapters that will remain after deletion (excluding the current one)
            chapters_to_renumber = list(
                ChapterMaster.objects.filter(bookmaster=bookmaster)
                .exclude(id=chaptermaster.id)
                .order_by("chapter_number")
            )
            total_remaining = len(chapters_to_renumber)

            # Delete the chaptermaster (and its associated chapters via CASCADE)
            response = super().form_valid(form)

            # Renumber all remaining chapters to be sequential starting from 1
            renumbered_count = 0
            for new_number, chapter in enumerate(chapters_to_renumber, start=1):
                if chapter.chapter_number != new_number:
                    chapter.chapter_number = new_number
                    chapter.save(update_fields=["chapter_number"])
                    renumbered_count += 1

            # Add success message with debug information
            if renumbered_count > 0:
                messages.success(
                    self.request,
                    f"Chapter {deleted_chapter_number} '{deleted_chapter_title}' deleted successfully. "
                    f"{renumbered_count} of {total_remaining} remaining chapters were automatically renumbered.",
                )
            else:
                messages.success(
                    self.request,
                    f"Chapter {deleted_chapter_number} '{deleted_chapter_title}' deleted successfully. "
                    f"No renumbering was needed for the {total_remaining} remaining chapters.",
                )

            return response

        except Exception as e:
            messages.error(
                self.request, f"Error deleting chapter: {str(e)}. Please try again."
            )
            # Re-raise to trigger rollback
            raise
