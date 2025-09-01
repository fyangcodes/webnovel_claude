from django.urls import path
from django.contrib.auth.views import (
    LogoutView,
    LoginView,
    PasswordChangeView,
    PasswordChangeDoneView,
)
from . import views

app_name = "accounts"

urlpatterns = [    
    # Authentication
    path(
        "login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        views.custom_logout,
        name="logout",
    ),
    path(
        "password_change/",
        PasswordChangeView.as_view(
            template_name="registration/password_change_form.html"
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    )
]
