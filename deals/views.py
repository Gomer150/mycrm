import json
from datetime import datetime, time
import calendar
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import smart_str
from django.db.models import Count
from django.views.decorators.http import require_http_methods, require_POST

from .forms import DealActionForm, DealForm, DocumentUploadForm
from .models import Company, Contact, Deal, DealAction, Document, Stage


ACTION_FORM_FIELDS = {
    "description",
    "status",
    "remind_at",
    "notify_before_value",
    "notify_before_unit",
    "recurrence",
    "custom_interval_days",
}


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
    if "notify_before_unit" not in data and data.get("notify_before_value"):
        data["notify_before_unit"] = DealAction.NotifyUnit.MINUTES

    return data


def _mark_overdue_actions(queryset):
    now = timezone.now()
    queryset.filter(
        starts_at__lt=now,
    ).exclude(
        status__in=[
            DealAction.Status.OVERDUE,
            DealAction.Status.COMPLETED,
            DealAction.Status.CANCELLED,
        ]
    ).update(status=DealAction.Status.OVERDUE)


STATUS_BADGE_CLASSES = {
    DealAction.Status.SCHEDULED: "text-bg-primary",
    DealAction.Status.IN_PROGRESS: "text-bg-warning",
    DealAction.Status.COMPLETED: "text-bg-success",
    DealAction.Status.OVERDUE: "text-bg-danger",
    DealAction.Status.CANCELLED: "text-bg-secondary",
}


def _decorate_actions(actions):
    for action in actions:
        action.status_badge_class = STATUS_BADGE_CLASSES.get(action.status, "text-bg-secondary")
        owner = action.deal.owner
        action.owner_display = owner.get_full_name() or owner.username
        local_dt = timezone.localtime(action.starts_at)
        action.local_datetime = local_dt
        action.local_date = local_dt.date()
        action.local_time = local_dt.time()
    return actions


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
        "status": action.status,
        "status_display": action.get_status_display(),
        "recurrence": action.recurrence,
        "recurrence_display": action.get_recurrence_display(),
        "custom_interval_days": action.custom_interval_days,
        "notify_before_value": action.notify_before_value,
        "notify_before_unit": action.notify_before_unit,
        "notify_before_unit_display": action.get_notify_before_unit_display()
        if action.notify_before_value is not None
        else "",
    }

    if action.remind_at:
        remind_at_local = timezone.localtime(action.remind_at)
        payload["remind_at"] = remind_at_local.isoformat()
        payload["remind_at_display"] = remind_at_local.strftime("%d.%m.%Y %H:%M")
        payload["remind_at_value"] = remind_at_local.strftime("%Y-%m-%dT%H:%M")

    return payload


def _serialize_contact(contact):
    return {
        "id": contact.id,
        "name": contact.name,
        "position": contact.position or "",
        "phone": contact.phone or "",
        "email": contact.email or "",
        "messengers": contact.messengers or "",
        "company_id": contact.company_id,
    }


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
    contacts = Contact.objects.filter(company=deal.client).order_by("name") if deal.client else Contact.objects.none()
    _mark_overdue_actions(deal.actions.all())
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
        deal.description = (request.POST.get("description") or "").strip()
        cost_raw = request.POST.get("cost")
        if cost_raw in ("", None):
            deal.cost = None
        else:
            try:
                normalized_cost = str(cost_raw).replace(",", ".")
                deal.cost = Decimal(normalized_cost)
            except (InvalidOperation, TypeError):
                pass
        deal.save()
        if "save_and_exit" in request.POST:
            return redirect("deals_list")
        return redirect("deal_edit", pk=deal.pk)

    companies_data = [
        {
            "id": company.id,
            "name": company.name,
            "phone": company.phone or "",
            "email": company.email or "",
            "address": company.address or "",
            "inn": company.inn or "",
            "website": company.website or "",
            "type": company.type,
            "type_display": company.get_type_display(),
        }
        for company in companies
    ]

    contacts_data = [_serialize_contact(contact) for contact in contacts]
    status_choices = DealAction.Status.choices
    status_options = [{"value": value, "label": label} for value, label in status_choices]
    notify_units_choices = DealAction.NotifyUnit.choices
    notify_units_options = [{"value": value, "label": label} for value, label in notify_units_choices]

    return render(
        request,
        "deals/deal_edit.html",
        {
            "deal": deal,
            "stages": stages,
            "companies": companies,  # 👈 передаём в шаблон
            "contacts": contacts,
            "companies_data": companies_data,
            "contacts_data": contacts_data,
            "actions": actions,
            "action_form": action_form,
            "recurrence_choices": recurrence_choices,
            "recurrence_options": recurrence_options,
            "status_choices": status_choices,
            "status_options": status_options,
            "notify_units_choices": notify_units_choices,
            "notify_units_options": notify_units_options,
            "default_notify_unit": DealAction.NotifyUnit.MINUTES,
        },
    )


@login_required
@require_http_methods(["POST"])
def create_company(request):
    name = request.POST.get("name")
    phone = request.POST.get("phone")
    email = request.POST.get("email")
    address = request.POST.get("address")
    inn = request.POST.get("inn", "")
    website = request.POST.get("website", "")

    if not name:
        return JsonResponse({"error": "Название клиента обязательно"}, status=400)

    def _normalize(value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    company = Company.objects.create(
        name=name,
        type="client",
        phone=_normalize(phone),
        email=_normalize(email),
        address=_normalize(address),
        inn=_normalize(inn),
        website=_normalize(website),
    )
    return JsonResponse(
        {
            "id": company.id,
            "name": company.name,
            "phone": company.phone or "",
            "email": company.email or "",
            "address": company.address or "",
            "inn": company.inn or "",
            "website": company.website or "",
            "type": company.type,
            "type_display": company.get_type_display(),
        }
    )


@login_required
@require_http_methods(["POST"])
def update_company(request, pk):
    company = get_object_or_404(Company, pk=pk)

    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    else:
        payload = request.POST.dict()

    name = (payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"errors": {"name": ["Укажите название клиента."]}}, status=400)

    def _normalize(value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    company.name = name
    company.phone = _normalize(payload.get("phone"))
    company.email = _normalize(payload.get("email"))
    company.address = _normalize(payload.get("address"))
    company.inn = _normalize(payload.get("inn"))
    company.website = _normalize(payload.get("website"))

    try:
        company.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    company.save()

    return JsonResponse(
        {
            "id": company.id,
            "name": company.name,
            "phone": company.phone or "",
            "email": company.email or "",
            "address": company.address or "",
            "inn": company.inn or "",
            "website": company.website or "",
            "type": company.type,
            "type_display": company.get_type_display(),
        }
    )


@login_required
@require_http_methods(["POST"])
def deal_contact_create(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)
    if not deal.client:
        return JsonResponse({"error": "Сначала выберите клиента для сделки."}, status=400)

    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    else:
        payload = request.POST.dict()

    def _normalize(value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    name = _normalize(payload.get("name"))
    if not name:
        return JsonResponse({"errors": {"name": ["Укажите имя контакта."]}}, status=400)

    contact = Contact(
        company=deal.client,
        owner=deal.owner,
        name=name,
        position=_normalize(payload.get("position")) or "",
        phone=_normalize(payload.get("phone")) or "",
        email=_normalize(payload.get("email")) or "",
        messengers=_normalize(payload.get("messengers")) or "",
    )

    try:
        contact.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    contact.save()
    return JsonResponse({"contact": _serialize_contact(contact)}, status=201)


@login_required
@require_http_methods(["POST"])
def deal_contact_update(request, pk, contact_id):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    contact = get_object_or_404(Contact, pk=contact_id)
    if deal.client_id and contact.company_id != deal.client_id:
        return JsonResponse({"error": "Контакт не относится к выбранному клиенту."}, status=400)

    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    else:
        payload = request.POST.dict()

    def _normalize(value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    name = _normalize(payload.get("name"))
    if not name:
        return JsonResponse({"errors": {"name": ["Укажите имя контакта."]}}, status=400)

    contact.name = name
    contact.position = _normalize(payload.get("position")) or ""
    contact.phone = _normalize(payload.get("phone")) or ""
    contact.email = _normalize(payload.get("email")) or ""
    contact.messengers = _normalize(payload.get("messengers")) or ""

    try:
        contact.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    contact.save()
    return JsonResponse({"contact": _serialize_contact(contact)})


@login_required
@require_http_methods(["POST"])
def deal_contact_delete(request, pk, contact_id):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    contact = get_object_or_404(Contact, pk=contact_id)
    if deal.client_id and contact.company_id != deal.client_id:
        return JsonResponse({"error": "Контакт не относится к выбранному клиенту."}, status=400)

    contact.delete()
    return JsonResponse({"status": "ok"})


@login_required
@require_http_methods(["GET"])
def company_contacts(request, pk):
    company = get_object_or_404(Company, pk=pk)
    contacts = company.contacts.all().order_by("name")
    return JsonResponse({"contacts": [_serialize_contact(contact) for contact in contacts]})


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
        actions_scope = DealAction.objects.all()
    else:
        deals = Deal.objects.filter(owner=request.user).order_by("-updated_at")
        actions_scope = DealAction.objects.filter(deal__owner=request.user)

    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(today, time.min), tz)
    day_end = timezone.make_aware(datetime.combine(today, time.max), tz)

    _mark_overdue_actions(actions_scope)

    todays_actions = list(
        actions_scope
        .filter(starts_at__range=(day_start, day_end))
        .exclude(status__in=[DealAction.Status.CANCELLED, DealAction.Status.COMPLETED])
        .select_related("deal", "deal__owner")
        .order_by("starts_at")
    )

    _decorate_actions(todays_actions)

    context = {
        "deals": deals,
        "todays_actions": todays_actions,
        "today_date": today,
    }
    return render(request, "deals/deals_list.html", context)


@login_required
def actions_list(request):
    if request.user.is_superuser:
        actions_scope = DealAction.objects.select_related('deal', 'deal__owner')
    else:
        actions_scope = DealAction.objects.select_related('deal', 'deal__owner').filter(deal__owner=request.user)

    view_type = request.GET.get('view', 'list')
    today = timezone.localdate()
    date_param = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_param, '%Y-%m-%d').date() if date_param else today
    except (ValueError, TypeError):
        selected_date = today

    if view_type == 'calendar':
        month_param = request.GET.get('month')
        year_param = request.GET.get('year')
        try:
            month = int(month_param) if month_param else selected_date.month
            year = int(year_param) if year_param else selected_date.year
        except (TypeError, ValueError):
            month, year = selected_date.month, selected_date.year
        if not 1 <= month <= 12:
            month = selected_date.month
        if year < 1:
            year = selected_date.year

        calendar_date = datetime(year, month, 1).date()
        tz = timezone.get_current_timezone()
        _, last_day = calendar.monthrange(year, month)
        month_start = timezone.make_aware(datetime.combine(calendar_date, time.min), tz)
        month_end_date = datetime(year, month, last_day).date()
        month_end = timezone.make_aware(datetime.combine(month_end_date, time.max), tz)

        _mark_overdue_actions(actions_scope.filter(starts_at__lte=month_end))
        month_actions = list(actions_scope.filter(starts_at__range=(month_start, month_end)).order_by('starts_at'))
        _decorate_actions(month_actions)

        actions_by_day = {}
        for action in month_actions:
            actions_by_day.setdefault(action.local_date, []).append(action)
        for day_actions in actions_by_day.values():
            day_actions.sort(key=lambda a: a.local_time)

        cal = calendar.Calendar(firstweekday=0)
        month_weeks = cal.monthdatescalendar(year, month)
        today_local = timezone.localdate()
        weeks = []
        for week in month_weeks:
            cells = []
            for day in week:
                cells.append({
                    'date': day,
                    'is_current_month': day.month == month,
                    'is_today': day == today_local,
                    'actions': actions_by_day.get(day, [])
                })
            weeks.append(cells)

        month_options = [(m, calendar.month_name[m]) for m in range(1, 13)]
        current_year = today.year
        year_range_start = min(current_year - 5, year - 2)
        year_range_end = max(current_year + 5, year + 2)
        year_options = list(range(year_range_start, year_range_end + 1))

        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

        context = {
            'view_type': 'calendar',
            'weeks': weeks,
            'calendar_month': month,
            'calendar_year': year,
            'month_name': calendar.month_name[month],
            'month_options': month_options,
            'year_options': year_options,
            'selected_date': selected_date,
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'day_names': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        }
        return render(request, 'deals/actions_calendar.html', context)

    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(selected_date, time.min), tz)
    day_end = timezone.make_aware(datetime.combine(selected_date, time.max), tz)

    _mark_overdue_actions(actions_scope.filter(starts_at__lte=day_end))
    day_actions = list(actions_scope.filter(starts_at__range=(day_start, day_end)).order_by('starts_at'))
    _decorate_actions(day_actions)

    context = {
        'actions': day_actions,
        'selected_date': selected_date,
        'view_type': 'list',
    }
    return render(request, 'deals/actions_list.html', context)


@login_required
def clients_list(request):
    clients = Company.objects.filter(type='client')
    if not request.user.is_superuser:
        clients = clients.filter(deals__owner=request.user)
    clients = (
        clients.annotate(deals_total=Count('deals', distinct=True))
        .order_by('name')
    )
    return render(request, 'deals/clients_list.html', {'clients': clients})


@login_required
def contacts_list(request):
    contacts = Contact.objects.select_related('company', 'owner').order_by('name')
    if not request.user.is_superuser:
        contacts = contacts.filter(owner=request.user)
    return render(request, 'deals/contacts_list.html', {'contacts': contacts})


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
