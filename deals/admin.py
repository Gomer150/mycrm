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
    list_display = ("name", "company_list", "position", "phone", "email")
    search_fields = ("name", "position", "phone", "email")
    list_filter = ("companies",)
    filter_horizontal = ("companies",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("companies")

    def company_list(self, obj):
        names = [company.name for company in obj.companies.all()[:5]]
        display = ", ".join(names)
        return display or "—"

    company_list.short_description = "Компании"

class DealCompanyInline(admin.TabularInline):
    model = DealCompany
    extra = 1

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "stage", "cost", "owner", "created_at", "updated_at")
    inlines = [DealCompanyInline]

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("filename", "deal", "uploader", "size", "uploaded_at")
    readonly_fields = ("size", "uploaded_at")
