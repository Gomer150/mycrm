from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.utils.encoding import smart_str
from django.conf import settings

from .models import Deal, Document, Stage
from .forms import DocumentUploadForm

def index(request):
    if request.user.is_authenticated:
        return redirect("deals_list")
    return render(request, "deals/deals_list.html", {"deals": []})

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
