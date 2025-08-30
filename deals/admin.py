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
