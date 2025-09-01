from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import User



@login_required
def custom_logout(request):
    """Custom logout view that handles both GET and POST requests"""
    from django.contrib.auth import logout
    from django.shortcuts import redirect

    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("accounts:login")
