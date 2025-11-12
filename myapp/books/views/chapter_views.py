from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    DeleteView,
    UpdateView,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
import difflib
import logging
from django.contrib.auth import get_user_model

from books.models import Book, Chapter
from books.forms import ChapterForm
from books.choices import ChapterProgress


# Chapter CRUD Views
class ChapterCreateView(LoginRequiredMixin, CreateView):
    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = get_object_or_404(
            Book, pk=self.kwargs["book_pk"], bookmaster__owner=self.request.user
        )
        context["book"] = book
        context["bookmaster"] = book.bookmaster
        return context

    def form_valid(self, form):
        book = get_object_or_404(
            Book, pk=self.kwargs["book_pk"], bookmaster__owner=self.request.user
        )
        form.instance.book = book

        # Create or get a ChapterMaster for this chapter
        # For now, we'll create a simple ChapterMaster with the same title
        from books.models import ChapterMaster

        chapter_number = book.chapters.count() + 1
        chaptermaster, created = ChapterMaster.objects.get_or_create(
            bookmaster=book.bookmaster,
            chapter_number=chapter_number,
            defaults={"canonical_title": form.instance.title},
        )
        form.instance.chaptermaster = chaptermaster

        response = super().form_valid(form)

        # Trigger AI analysis for original language chapters with content
        if (
            self.object.content
            and self.object.book.language == self.object.book.bookmaster.original_language
        ):
            from books.tasks import analyze_chapter_entities
            analyze_chapter_entities.delay(self.object.id)

        messages.success(
            self.request, f"Chapter '{form.instance.title}' created successfully!"
        )
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.kwargs["book_pk"]})


class ChapterDetailView(LoginRequiredMixin, DetailView):
    model = Chapter
    template_name = "books/chapter/detail.html"
    context_object_name = "chapter"

    def get_queryset(self):
        user = self.request.user
        User = get_user_model()
        if not user.is_authenticated or not isinstance(user, User):
            return Chapter.objects.none()
        return Chapter.objects.filter(book__bookmaster__owner=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = context.get("chapter")
        if chapter:
            context["book"] = chapter.book
            context["bookmaster"] = chapter.book.bookmaster
            context["chaptermaster"] = chapter.chaptermaster
            # Check if chapter has context
            if hasattr(chapter, 'context'):
                context["chapter_context"] = chapter.context
        return context


class ChapterUpdateView(LoginRequiredMixin, UpdateView):
    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"
    context_object_name = "chapter"

    def get_queryset(self):
        return Chapter.objects.filter(book__bookmaster__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.object.book
        context["bookmaster"] = self.object.book.bookmaster
        context["chaptermaster"] = self.object.chaptermaster
        return context

    def get_success_url(self):
        return reverse_lazy("books:chapter_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        # Check if content changed before saving
        content_changed = False
        if 'content' in form.changed_data:
            content_changed = True

        response = super().form_valid(form)

        # Trigger AI analysis if content changed and it's original language
        if (
            content_changed
            and self.object.content
            and self.object.book.language == self.object.book.bookmaster.original_language
        ):
            from books.tasks import analyze_chapter_entities
            analyze_chapter_entities.delay(self.object.id)

        messages.success(
            self.request, f"Chapter '{form.instance.title}' updated successfully!"
        )
        return response


class ChapterDeleteView(LoginRequiredMixin, DeleteView):
    model = Chapter
    template_name = "books/chapter/confirm_delete.html"

    def get_queryset(self):
        return Chapter.objects.filter(book__bookmaster__owner=self.request.user)

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.book.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.object.book
        context["bookmaster"] = self.object.book.bookmaster
        context["chaptermaster"] = self.object.chaptermaster
        return context
