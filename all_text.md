=== FILE START: /var/www/crm/deals/migrations/__init__.py ===
```python
```
=== FILE END: /var/www/crm/deals/migrations/__init__.py ===

=== FILE START: /var/www/crm/deals/models.py ===
```python
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User


User = get_user_model()

class Stage(models.Model):
    name = models.CharField(max_length=120)
    order_index = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class Company(models.Model):
    TYPE_CHOICES = [
        ("client", "Клиент"),
        ("partner", "Партнёр"),
        ("supplier", "Поставщик"),
    ]
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="client")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Contact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    messengers = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.name:  
            # Считаем количество сделок
            count = Deal.objects.filter(owner=self.owner).count() + 1
            self.name = f"Сделка {count}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

class Deal(models.Model):
    title = models.CharField(max_length=255)
    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True)
    companies = models.ManyToManyField(Company, through="DealCompany", related_name="deals")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Автогенерация имени сделки
        if not self.title:
            count = Deal.objects.filter(owner=self.owner).count() + 1
            self.title = f"Сделка {count}"
        # Автоматический этап для новых сделок
        if not self.stage:
            # Получаем объект Stage с названием "Заявка"
            stage_obj = Stage.objects.filter(name="Заявка").first()
            self.stage = stage_obj
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class DealCompany(models.Model):
    ROLE_CHOICES = [
        ("client", "Клиент"),
        ("partner", "Партнёр"),
        ("supplier", "Поставщик"),
    ]
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("deal", "company", "role")

class Document(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="documents")
    filename = models.CharField(max_length=512)
    content_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    data = models.BinaryField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.filename} ({self.size} bytes)"```
=== FILE END: /var/www/crm/deals/models.py ===

=== FILE START: /var/www/crm/deals/__init__.py ===
```python
# black hole
```
=== FILE END: /var/www/crm/deals/__init__.py ===

=== FILE START: /var/www/crm/deals/admin.py ===
```python
from django.contrib import admin
from .models import Stage, Company, Contact, Deal, DealCompany, Document

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("name", "order_index")

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "created_at")

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "position", "phone", "email")

class DealCompanyInline(admin.TabularInline):
    model = DealCompany
    extra = 1

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "stage", "owner", "created_at", "updated_at")
    inlines = [DealCompanyInline]

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("filename", "deal", "uploader", "size", "uploaded_at")
    readonly_fields = ("size", "uploaded_at")
```
=== FILE END: /var/www/crm/deals/admin.py ===

=== FILE START: /var/www/crm/deals/forms.py ===
```python
from django import forms

class DocumentUploadForm(forms.Form):
    file = forms.FileField()
```
=== FILE END: /var/www/crm/deals/forms.py ===

=== FILE START: /var/www/crm/deals/apps.py ===
```python
from django.apps import AppConfig

class DealsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "deals"
```
=== FILE END: /var/www/crm/deals/apps.py ===

=== FILE START: /var/www/crm/deals/templates/deals/upload_document.html ===
```html
{% extends "deals/base.html" %}
{% block content %}
<h3>Загрузить документ — {{ deal.title }}</h3>
<form method="post" enctype="multipart/form-data">
  {% csrf_token %}
  {{ form.non_field_errors }}
  <div class="mb-3">
    {{ form.file.label_tag }}<br>
    {{ form.file }}
    {% for err in form.file.errors %}<div class="text-danger">{{ err }}</div>{% endfor %}
  </div>
  <button class="btn btn-success" type="submit">Загрузить</button>
  <a class="btn btn-secondary" href="{% url 'deal_detail' deal.pk %}">Отмена</a>
</form>
{% endblock %}
```
=== FILE END: /var/www/crm/deals/templates/deals/upload_document.html ===

=== FILE START: /var/www/crm/deals/templates/deals/login.html ===
```html
<!DOCTYPE html>
<html>
<head>
    <title>Вход в CRM</title>
</head>
<body>
<h2>Вход в CRM</h2>
<form method="post">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit">Войти</button>
</form>
</body>
</html>
```
=== FILE END: /var/www/crm/deals/templates/deals/login.html ===

=== FILE START: /var/www/crm/deals/templates/deals/deals_list.html ===
```html
{% extends "deals/base.html" %}
{% block content %}
<h1>Сделки</h1>
<table class="table table-striped">
  <thead><tr><th>Название</th><th>Этап</th><th>Владелец</th><th>Обновлено</th></tr></thead>
  <tbody>
    {% for deal in deals %}
    <tr>
      <td><a href="{% url 'deal_edit' deal.pk %}">{{ deal.title }}</a></td>
      <td>{{ deal.stage }}</td>
      <td>{{ deal.owner.username }}</td>
      <td>{{ deal.updated_at }}</td>
    </tr>
    {% empty %}
    <tr><td colspan="4">Сделок нет</td></tr>
    {% endfor %}
  </tbody>
</table>

<button id="add-deal-btn" class="btn btn-primary mt-3">Добавить сделку</button>

<script>
document.getElementById("add-deal-btn").addEventListener("click", function() {
  fetch("/deals/create/", {
    method: "POST",
    headers: {
      "X-CSRFToken": "{{ csrf_token }}",
    }
  })
  .then(response => response.json())
  .then(data => {
    // добавляем новую строку в таблицу
    let tbody = document.querySelector("table tbody");
    let tr = document.createElement("tr");
    tr.innerHTML = `
      <td><a href="/deals/${data.id}/edit/">${data.name}</a></td>
      <td>${data.stage}</td>
      <td>{{ request.user.username }}</td>
      <td>${data.created_at}</td>
    `;
    tbody.appendChild(tr);
  });
});
</script>

{% endblock %}

```
=== FILE END: /var/www/crm/deals/templates/deals/deals_list.html ===

=== FILE START: /var/www/crm/deals/templates/deals/base.html ===
```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Моя любимая CRM</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-3">
  <div class="container-fluid">
    <a class="navbar-brand" href="/">Моя любимая CRM</a>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav ms-auto">
        {% if user.is_authenticated %}
        <li class="nav-item"><a class="nav-link" href="#">{{ user.username }}</a></li>
        <li class="nav-item"><a class="nav-link" href="/admin/logout/">Logout</a></li>
        {% else %}
        <li class="nav-item"><a class="nav-link" href="/admin/login/">Login</a></li>
        {% endif %}
      </ul>
    </div>
  </div>
</nav>

<div class="container">
  {% block content %}{% endblock %}
</div>
</body>
</html>
```
=== FILE END: /var/www/crm/deals/templates/deals/base.html ===

=== FILE START: /var/www/crm/deals/templates/deals/deal_detail.html ===
```html
{% extends "deals/base.html" %}
{% block content %}

<h2>Редактирование сделки</h2>

<form method="post" action="{% url 'deal_edit' deal.pk %}">
  {% csrf_token %}

  <div class="mb-3">
    <label for="title" class="form-label">Название сделки</label>
    <input type="text" class="form-control" id="title" name="title" value="{{ deal.title }}">
  </div>

  <div class="mb-3">
    <label for="stage" class="form-label">Этап</label>
    <select class="form-select" id="stage" name="stage_id">
      {% for s in stages %}
        <option value="{{ s.id }}" {% if deal.stage_id == s.id %}selected{% endif %}>
          {{ s.order_index }} — {{ s.name }}
        </option>
      {% endfor %}
    </select>
  </div>

  <div class="mb-3">
    <label for="client" class="form-label">Клиент (ID)</label>
    <input type="number" class="form-control" id="client" name="client_id" value="{{ deal.client_id }}">
  </div>

  <div class="mb-3">
    <label class="form-label">Владелец</label>
    <input type="text" class="form-control" value="{{ deal.owner.username }}" disabled>
  </div>

  <button type="submit" class="btn btn-success">Сохранить</button>
</form>

<hr>

<h4>Документы</h4>
<ul>
  {% for doc in deal.documents.all %}
  <li>
    {{ doc.filename }} —
    <a href="{% url 'download_document' doc.pk %}">скачать</a>
  </li>
  {% empty %}
  <li>Нет документов</li>
  {% endfor %}
</ul>

<a class="btn btn-primary" href="{% url 'upload_document' deal.pk %}">Загрузить документ</a>

{% endblock %}
```
=== FILE END: /var/www/crm/deals/templates/deals/deal_detail.html ===

=== FILE START: /var/www/crm/deals/templates/deals/deal_edit.html ===
```html
{% extends "deals/base.html" %}
{% block content %}

<h2>Редактирование сделки</h2>

<form method="post" action="{% url 'deal_edit' deal.pk %}">
  {% csrf_token %}

  <div class="mb-3">
    <label for="title" class="form-label">Название сделки</label>
    <input type="text" class="form-control" id="title" name="title" value="{{ deal.title }}">
  </div>

  <div class="mb-3">
    <label for="stage" class="form-label">Этап</label>
    <select class="form-select" id="stage" name="stage_id">
      {% for s in stages %}
        <option value="{{ s.id }}" {% if deal.stage_id == s.id %}selected{% endif %}>
          {{ s.order_index }} — {{ s.name }}
        </option>
      {% endfor %}
    </select>
  </div>

  <div class="mb-3">
    <label for="client" class="form-label">Клиент (ID)</label>
<!--    <input type="number" class="form-control" id="client" name="client_id" value="{{ deal.client_id }}"> -->
    <input type="number" class="form-control" value="{{ deal.client_id }}" disabled>
  </div>

  <div class="mb-3">
    <label class="form-label">Владелец</label>
    <input type="text" class="form-control" value="{{ deal.owner.username }}" disabled>
  </div>

  <button type="submit" class="btn btn-success">Сохранить</button>
</form>

<hr>

<h4>Документы</h4>
<ul>
  {% for doc in deal.documents.all %}
  <li>
    {{ doc.filename }} —
    <a href="{% url 'download_document' doc.pk %}">скачать</a>
  </li>
  {% empty %}
  <li>Нет документов</li>
  {% endfor %}
</ul>

<a class="btn btn-primary" href="{% url 'upload_document' deal.pk %}">Загрузить документ</a>

{% endblock %}
```
=== FILE END: /var/www/crm/deals/templates/deals/deal_edit.html ===

=== FILE START: /var/www/crm/deals/views.py ===
```python
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.utils.encoding import smart_str
from django.conf import settings
from django.http import JsonResponse


from .models import Deal, Document, Stage
from .forms import DocumentUploadForm

def index(request):
    if request.user.is_authenticated:
        return redirect("deals_list")
    return render(request, "deals/deals_list.html", {"deals": []})

@login_required
def create_deal(request):
    if request.method == "POST":
        deal = Deal.objects.create(owner=request.user)
        deal.save()
        return JsonResponse({
            "id": deal.id,
            "name": deal.title,
            "Title": deal.title,
            "created_at": deal.created_at.strftime("%Y-%m-%d %H:%M")
        })

def deal_edit(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    stages = Stage.objects.all()

    if request.method == "POST":
        deal.title = request.POST.get("title")
        deal.stage_id = request.POST.get("stage_id")
        deal.client_id = request.POST.get("client_id")
        deal.save()
        return redirect("deal_detail", pk=deal.pk)

    return render(request, "deals/deal_edit.html", {"deal": deal, "stages": stages})

@login_required
def deals_list(request):
    if request.user.is_superuser:
        deals = Deal.objects.all().order_by("-updated_at")
    else:
        deals = Deal.objects.filter(owner=request.user).order_by("-updated_at")
    return render(request, "deals/deals_list.html", {"deals": deals})

@login_required
def deal_detail(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return HttpResponseForbidden("Нет доступа")
    stages = Stage.objects.all().order_by("order_index")
    return render(request, "deals/deal_detail.html", {"deal": deal, "stages": stages})

@login_required
def upload_document(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return HttpResponseForbidden("Нет доступа")
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            max_size = getattr(settings, "MAX_UPLOAD_SIZE", 200 * 1024 * 1024)
            if f.size > max_size:
                form.add_error("file", f"Файл слишком большой. Максимум {max_size} байт.")
            else:
                chunks = []
                for chunk in f.chunks():
                    chunks.append(chunk)
                blob = b"".join(chunks)
                Document.objects.create(
                    deal=deal,
                    filename=f.name,
                    content_type=getattr(f, "content_type", ""),
                    size=f.size,
                    data=blob,
                    uploader=request.user,
                )
                return redirect("deal_detail", pk=deal.pk)
    else:
        form = DocumentUploadForm()
    return render(request, "deals/upload_document.html", {"form": form, "deal": deal})

@login_required
def download_document(request, doc_id):
    doc = get_object_or_404(Document, pk=doc_id)
    if not (request.user.is_superuser or doc.deal.owner == request.user):
        return HttpResponseForbidden("Нет доступа")
    response = HttpResponse(doc.data, content_type=doc.content_type or "application/octet-stream")
    response["Content-Length"] = str(doc.size)
    response["Content-Disposition"] = f'attachment; filename="{smart_str(doc.filename)}"'
    return response
```
=== FILE END: /var/www/crm/deals/views.py ===

=== FILE START: /var/www/crm/deals/urls.py ===
```python
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from deals import views as deals_views
from django.urls import path
from . import views

urlpatterns = [

    path('', deals_views.index, name='home'),  # главная страница
    path('deals/', deals_views.deals_list, name='deals_list'),
    path('deals/<int:pk>/edit/', deals_views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/', deals_views.deal_detail, name='deal_detail'),
    path('deals/<int:pk>/upload/', deals_views.upload_document, name='upload_document'),
    path('document/<int:doc_id>/download/', deals_views.download_document, name='download_document'),
    path("deals/create/", views.create_deal, name="create_deal"),


]
```
=== FILE END: /var/www/crm/deals/urls.py ===

=== FILE START: /var/www/crm/crm_project/wsgi.py ===
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm_project.settings")
application = get_wsgi_application()
```
=== FILE END: /var/www/crm/crm_project/wsgi.py ===

=== FILE START: /var/www/crm/crm_project/__init__.py ===
```python
# пусто
```
=== FILE END: /var/www/crm/crm_project/__init__.py ===

=== FILE START: /var/www/crm/crm_project/settings.py ===
```python
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "n4x2&v$8#k+2j3r%yq5@l^9g7b!e0x)q4@h8o2u)k_r&jz4n^")
DEBUG = os.getenv("DEBUG", "True") == "True"
# ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,192.168.1.200").split(",")
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "192.168.1.200"]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'   # после логина редиректит на главную


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "deals",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "crm_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "deals" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    },
]

WSGI_APPLICATION = "crm_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Upload / BLOB-specific settings
FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440  # 2.5 MB: larger goes to temp file
MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB limit for writing to DB

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ru-RU"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Since we store files in DB, MEDIA settings are minimal
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```
=== FILE END: /var/www/crm/crm_project/settings.py ===

=== FILE START: /var/www/crm/crm_project/urls.py ===
```python
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Админка
    path('admin/', admin.site.urls),

    # Аутентификация
    path('accounts/login/', auth_views.LoginView.as_view(template_name="deals/login.html"), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),

    # Подключение путей приложения deals
    path('', include('deals.urls')),  # Все пути из deals/urls.py будут работать
]

```
=== FILE END: /var/www/crm/crm_project/urls.py ===

=== FILE START: /var/www/crm/manage.py ===
```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django not installed") from exc
    execute_from_command_line(sys.argv)
```
=== FILE END: /var/www/crm/manage.py ===

