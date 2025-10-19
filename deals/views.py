import json
from datetime import datetime, time
import calendar
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse, QueryDict
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
    if "status" not in data:
        data["status"] = DealAction.Status.SCHEDULED
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


def _serialize_contact(contact, primary_company_id=None):
    companies_qs = getattr(contact, '_prefetched_objects_cache', {}).get('companies')
    if companies_qs is None:
        companies_qs = contact.companies.all()
    company_ids = [company.id for company in companies_qs]
    companies_payload = [
        {"id": company.id, "name": company.name}
        for company in companies_qs
    ]
    if primary_company_id is None:
        primary_company_id = company_ids[0] if company_ids else None
    primary_company_name = None
    for company in companies_payload:
        if company["id"] == primary_company_id:
            primary_company_name = company["name"]
            break
    return {
        "id": contact.id,
        "name": contact.name,
        "position": contact.position or "",
        "phone": contact.phone or "",
        "email": contact.email or "",
        "messengers": contact.messengers or "",
        "company_id": primary_company_id,
        "primary_company_name": primary_company_name or "",
        "company_ids": company_ids,
        "companies": companies_payload,
    }


def _unique_int_list(values):
    if not values:
        return []
    normalized = []
    seen = set()
    for value in values:
        try:
            integer = int(value)
        except (TypeError, ValueError):
            continue
        if integer in seen:
            continue
        seen.add(integer)
        normalized.append(integer)
    return normalized


def _extract_company_ids(payload):
    if payload is None:
        return None
    keys = ("company_ids", "companies", "company_ids[]", "companies[]")
    raw = None
    if isinstance(payload, QueryDict):
        for key in keys:
            if key in payload:
                raw = payload.getlist(key)
                break
        if raw is None:
            return None
    else:
        for key in ("company_ids", "companies"):
            if key in payload:
                raw = payload[key]
                break
        if raw is None:
            return None
    if isinstance(raw, (list, tuple, set)):
        candidates = list(raw)
    elif raw in (None, ""):
        candidates = []
    elif isinstance(raw, str):
        candidates = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        candidates = [raw]
    return _unique_int_list(candidates)


def _extract_primary_company_id(payload):
    if payload is None:
        return None
    keys = ("primary_company_id", "primary_company")
    value = None
    if isinstance(payload, QueryDict):
        for key in keys:
            if key in payload:
                value = payload.get(key)
                break
    else:
        for key in keys:
            if key in payload:
                value = payload[key]
                break
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_primary_company_id(primary_company_id, company_ids, fallback=None):
    if not company_ids:
        return None
    if primary_company_id in company_ids:
        return primary_company_id
    if fallback in company_ids:
        return fallback
    return company_ids[0]


def _ordered_companies_by_ids(company_ids):
    if not company_ids:
        return [], []
    companies = list(Company.objects.filter(id__in=company_ids))
    mapping = {company.id: company for company in companies}
    ordered = [mapping[cid] for cid in company_ids if cid in mapping]
    missing = [cid for cid in company_ids if cid not in mapping]
    return ordered, missing



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
    contacts = Contact.objects.filter(companies=deal.client).prefetch_related('companies').order_by("name") if deal.client else Contact.objects.none()
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

    contacts_data = [_serialize_contact(contact, deal.client_id) for contact in contacts]
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
        payload = request.POST

    def _normalize(value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    contact_id_raw = _normalize(payload.get("contact_id"))
    contact = None
    is_existing_contact = False
    if contact_id_raw:
        try:
            contact_identifier = int(contact_id_raw)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Контакт не найден."}, status=404)
        contact = Contact.objects.filter(pk=contact_identifier).first()
        if contact is None:
            return JsonResponse({"error": "Контакт не найден."}, status=404)
        is_existing_contact = True
    else:
        name = _normalize(payload.get("name"))
        if not name:
            return JsonResponse({"errors": {"name": ["Укажите имя контакта."]}}, status=400)
        contact = Contact(
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

    company_ids = _extract_company_ids(payload)
    if company_ids is None:
        company_ids = []
    if deal.client_id and deal.client_id not in company_ids:
        company_ids.insert(0, deal.client_id)
    company_ids = _unique_int_list(company_ids)
    if not company_ids:
        return JsonResponse({"errors": {"company_ids": ["Укажите хотя бы одну компанию для контакта."]}}, status=400)

    companies, missing = _ordered_companies_by_ids(company_ids)
    if missing:
        return JsonResponse({"errors": {"company_ids": [f"Компания с ID {missing[0]} не найдена."]}}, status=400)

    if is_existing_contact:
        contact.companies.add(*companies)
    else:
        contact.companies.set(companies)

    contact = Contact.objects.prefetch_related('companies').get(pk=contact.pk)
    actual_company_ids = [company.id for company in contact.companies.all()]
    primary_company_id = _extract_primary_company_id(payload)
    primary_company_id = _resolve_primary_company_id(primary_company_id, actual_company_ids, fallback=deal.client_id)

    contact_data = _serialize_contact(contact, primary_company_id)
    return JsonResponse({"contact": contact_data}, status=201)


@login_required
@require_http_methods(["POST"])
def deal_contact_update(request, pk, contact_id):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    contact = get_object_or_404(Contact.objects.prefetch_related('companies'), pk=contact_id)
    if deal.client_id and not contact.companies.filter(pk=deal.client_id).exists():
        return JsonResponse({"error": "Контакт не относится к выбранному клиенту."}, status=400)

    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    else:
        payload = request.POST

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

    company_ids = _extract_company_ids(payload)
    if company_ids is not None:
        company_ids = _unique_int_list(company_ids)
        if not company_ids:
            return JsonResponse({"errors": {"company_ids": ["Укажите хотя бы одну компанию для контакта."]}}, status=400)
        companies, missing = _ordered_companies_by_ids(company_ids)
        if missing:
            return JsonResponse({"errors": {"company_ids": [f"Компания с ID {missing[0]} не найдена."]}}, status=400)
        contact.companies.set(companies)

    try:
        contact.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    contact.save()
    contact = Contact.objects.prefetch_related('companies').get(pk=contact.pk)
    actual_company_ids = [company.id for company in contact.companies.all()]
    primary_company_id = _extract_primary_company_id(payload)
    primary_company_id = _resolve_primary_company_id(primary_company_id, actual_company_ids, fallback=deal.client_id)

    return JsonResponse({"contact": _serialize_contact(contact, primary_company_id)})


@login_required
@require_http_methods(["POST"])
def deal_contact_delete(request, pk, contact_id):
    deal = get_object_or_404(Deal, pk=pk)
    if not (request.user.is_superuser or deal.owner == request.user):
        return JsonResponse({"error": "Нет доступа"}, status=403)

    contact = get_object_or_404(Contact.objects.prefetch_related('companies'), pk=contact_id)
    if deal.client_id and not contact.companies.filter(pk=deal.client_id).exists():
        return JsonResponse({"error": "Контакт не относится к выбранному клиенту."}, status=400)

    if deal.client_id:
        contact.companies.remove(deal.client)

    if contact.companies.exists():
        contact.save(update_fields=[])
    else:
        contact.delete()
    return JsonResponse({"status": "ok"})


@login_required
@require_http_methods(["GET"])
def company_contacts(request, pk):
    company = get_object_or_404(Company, pk=pk)
    contacts = company.contacts.prefetch_related('companies').order_by("name")
    payload = [_serialize_contact(contact, company.id) for contact in contacts]
    return JsonResponse({"contacts": payload})


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

    start_param = request.GET.get('start_date')
    end_param = request.GET.get('end_date')
    status_param = request.GET.get('status')

    valid_statuses = {choice[0] for choice in DealAction.Status.choices}
    selected_status = status_param if status_param in valid_statuses else 'all'

    if selected_status != 'all':
        actions_scope = actions_scope.filter(status=selected_status)

    def _parse_date(value, fallback):
        if not value:
            return fallback
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return fallback

    start_date = _parse_date(start_param, selected_date)
    end_date = _parse_date(end_param, start_date)

    if end_date < start_date:
        start_date, end_date = end_date, start_date

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
            'selected_status': selected_status,
            'status_options': DealAction.Status.choices,
        }
        return render(request, 'deals/actions_calendar.html', context)

    tz = timezone.get_current_timezone()
    range_start = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    range_end = timezone.make_aware(datetime.combine(end_date, time.max), tz)

    _mark_overdue_actions(actions_scope.filter(starts_at__lte=range_end))
    range_actions = list(actions_scope.filter(starts_at__range=(range_start, range_end)).order_by('starts_at'))
    _decorate_actions(range_actions)

    context = {
        'actions': range_actions,
        'start_date': start_date,
        'end_date': end_date,
        'view_type': 'list',
        'selected_date': start_date,
        'selected_status': selected_status,
        'status_options': DealAction.Status.choices,
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
    contacts = Contact.objects.prefetch_related('companies').select_related('owner').order_by('name')
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
