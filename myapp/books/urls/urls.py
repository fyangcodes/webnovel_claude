from django.urls import path
from books import views

app_name = "books"

# Regular URL patterns
urlpatterns = [
    # BookMaster (Work/Series) list view / Home page
    path("", views.BookMasterListView.as_view(), name="bookmaster_list"),
    # BookMaster (Work/Series) CRUD views
    path("bookmasters/create/", views.BookMasterCreateView.as_view(), name="bookmaster_create"),
    path("bookmasters/<int:pk>/", views.BookMasterDetailView.as_view(), name="bookmaster_detail"),
    path("bookmasters/<int:pk>/update/", views.BookMasterUpdateView.as_view(), name="bookmaster_update"),
    path("bookmasters/<int:pk>/delete/", views.BookMasterDeleteView.as_view(), name="bookmaster_delete"),

    # ChapterMaster (Chapter) views under a BookMaster
    path("chaptermasters/create/to/bookmasters/<int:bookmaster_pk>/", views.ChapterMasterCreateView.as_view(), name="chaptermaster_create"),
    path("chaptermasters/<int:pk>/", views.ChapterMasterDetailView.as_view(), name="chaptermaster_detail"),
    path("chaptermasters/<int:pk>/update/", views.ChapterMasterUpdateView.as_view(), name="chaptermaster_update"),
    path("chaptermasters/<int:pk>/delete/", views.ChapterMasterDeleteView.as_view(), name="chaptermaster_delete"),

    # Book (Translation/Edition) views under a BookMaster
    path("books/create/to/bookmasters/<int:bookmaster_pk>/", views.BookCreateView.as_view(), name="book_create"),
    path("books/<int:pk>/", views.BookDetailView.as_view(), name="book_detail"),
    path("books/<int:pk>/update/", views.BookUpdateView.as_view(), name="book_update"),
    path("books/<int:pk>/delete/", views.BookDeleteView.as_view(), name="book_delete"),
    #path("books/<int:pk>/upload-file/", views.BookFileUploadView.as_view(), name="bookfile_upload"), 

    # Chapter CRUD views
    path("chapters/create/to/books/<int:book_pk>/", views.ChapterCreateView.as_view(), name="chapter_create"),
    path("chapters/<int:pk>/", views.ChapterDetailView.as_view(), name="chapter_detail"),
    path("chapters/<int:pk>/update/", views.ChapterUpdateView.as_view(), name="chapter_update"),
    path("chapters/<int:pk>/delete/", views.ChapterDeleteView.as_view(), name="chapter_delete"),
        
    # Chapter translation views
    path("chapters/<int:chapter_id>/translate/<str:language_code>/", views.ChapterTranslationView.as_view(), name="chapter_translate"),
    #path("chapters/<int:pk>/check-translation-status/", CheckTranslationStatusView.as_view(), name="chapter_check_translation_status"),
    #path("chapters/<int:pk>/changelog/", ChapterChangelogView.as_view(), name="chapter_changelog"),
    #path("chapters/<int:pk>/compare/", ChapterVersionCompareView.as_view(), name="chapter_version_compare"),
    #path("chapters/diff/", ChapterDiffView.as_view(), name="chapter_diff"),
    
    # Chapter schedule and publish
    #path("chapters/<int:pk>/schedule/", ChapterScheduleView.as_view(), name="chapter_schedule"),
    #path("chapters/<int:pk>/publish/", ChapterPublishNowView.as_view(), name="chapter_publish_now"),
    
    # Batch processing views
    #path("batch-analyze-chapters/", BatchAnalyzeChaptersView.as_view(), name="batch_analyze_chapters"),
    
    # Chapter analyze views
    path("chapters/<int:pk>/analyze/", views.ChapterAnalyzeView.as_view(), name="chapter_analyze"),
    path("task-status/", views.TaskStatusView.as_view(), name="task_status"),
    
]
