import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import smart_str
from django.views.decorators.http import require_http_methods, require_POST

from .forms import DealActionForm, DealForm, DocumentUploadForm
from .models import Company, Deal, DealAction, Document, Stage


ACTION_FORM_FIELDS = {"description", "remind_at", "recurrence", "custom_interval_days"}


def _get_action_form_data(request):
    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    else:
        payload = request.POST.dict()

    data = {}
    for field in ACTION_FORM_FIELDS:
        if field in payload:
            value = payload[field]
            if value in (None, False):
                data[field] = ""
            elif isinstance(value, (int, float)):
                data[field] = str(value)
            else:
                data[field] = value

    if "recurrence" not in data:
        data["recurrence"] = DealAction.Recurrence.NONE

    return data


def _serialize_action(action):
    starts_at_local = timezone.localtime(action.starts_at)
    payload = {
        "id": action.id,
        "description": action.description,
        "starts_at": starts_at_local.isoformat(),
        "starts_at_display": starts_at_local.strftime("%d.%m.%Y %H:%M"),
        "remind_at": None,
        "remind_at_display": "",
        "remind_at_value": "",
        "recurrence": action.recurrence,
        "recurrence_display": action.get_recurrence_display(),
        "custom_interval_days": action.custom_interval_days,
    }

    if action.remind_at:
        remind_at_local = timezone.localtime(action.remind_at)
        payload["remind_at"] = remind_at_local.isoformat()
        payload["remind_at_display"] = remind_at_local.strftime("%d.%m.%Y %H:%M")
        payload["remind_at_value"] = remind_at_local.strftime("%Y-%m-%dT%H:%M")

    return payload


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

@login_required
def deal_edit(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return HttpResponseForbidden("Нет доступа")
    stages = Stage.objects.all()
    companies = Company.objects.all()  # 👈 добавляем список клиентов
    actions = deal.actions.all()
    action_form = DealActionForm()
    recurrence_choices = DealAction.Recurrence.choices
    recurrence_options = [
        {"value": value, "label": label} for value, label in recurrence_choices
    ]

    if request.method == "POST":
        deal.title = request.POST.get("title")
        deal.stage_id = request.POST.get("stage_id")
        deal.client_id = request.POST.get("client_id") or None
        cost_raw = request.POST.get("cost")
        if cost_raw in ("", None):
            deal.cost = None
        else:
            try:
                deal.cost = Decimal(cost_raw)
            except (InvalidOperation, TypeError):
                pass
        deal.save()
        return redirect("deal_edit", pk=deal.pk)

    return render(
        request,
        "deals/deal_edit.html",
        {
            "deal": deal,
            "stages": stages,
            "companies": companies,  # 👈 передаём в шаблон
            "actions": actions,
            "action_form": action_form,
            "recurrence_choices": recurrence_choices,
            "recurrence_options": recurrence_options,
        },
    )


@login_required
@require_http_methods(["POST"])
def create_company(request):
    name = request.POST.get("name")
    phone = request.POST.get("phone")
    email = request.POST.get("email")
    address = request.POST.get("address")

    if not name:
        return JsonResponse({"error": "Название клиента обязательно"}, status=400)

    company = Company.objects.create(
        name=name,
        type="client",
        phone=phone,
        email=email,
        address=address,
    )
    return JsonResponse({"id": company.id, "name": company.name})


@login_required
@require_http_methods(["POST"])
def deal_action_create(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    form = DealActionForm(_get_action_form_data(request))
    if form.is_valid():
        action = form.save(commit=False)
        action.deal = deal
        action.save()
        return JsonResponse({"action": _serialize_action(action)}, status=201)

    return JsonResponse({"errors": form.errors}, status=400)


@login_required
@require_http_methods(["POST"])
def deal_action_update(request, pk, action_id):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    action = get_object_or_404(DealAction, pk=action_id, deal=deal)
    form = DealActionForm(_get_action_form_data(request), instance=action)
    if form.is_valid():
        action = form.save()
        return JsonResponse({"action": _serialize_action(action)})

    return JsonResponse({"errors": form.errors}, status=400)


@login_required
@require_http_methods(["POST"])
def deal_action_delete(request, pk, action_id):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    action = get_object_or_404(DealAction, pk=action_id, deal=deal)
    action.delete()
    return JsonResponse({"status": "ok"})


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
                return redirect("deal_edit", pk=deal.pk)
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

@login_required
def delete_document(request, doc_id):
    doc = get_object_or_404(Document, pk=doc_id)
    if not (request.user.is_superuser or doc.deal.owner == request.user):
        return HttpResponseForbidden("Нет доступа")
    deal_id = doc.deal.pk
    doc.delete()
    return redirect("deal_edit", pk=deal_id)
