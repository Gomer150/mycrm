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
    path('deals/<int:pk>/', deals_views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/upload/', deals_views.upload_document, name='upload_document'),
    path('deals/<int:pk>/actions/create/', views.deal_action_create, name='deal_action_create'),
    path('deals/<int:pk>/actions/<int:action_id>/update/', views.deal_action_update, name='deal_action_update'),
    path('deals/<int:pk>/actions/<int:action_id>/delete/', views.deal_action_delete, name='deal_action_delete'),
    path('document/<int:doc_id>/download/', deals_views.download_document, name='download_document'),
    path("deals/create/", views.create_deal, name="create_deal"),
    path("document/<int:doc_id>/delete/", views.delete_document, name="delete_document"),
    path("companies/create/", views.create_company, name="create_company"),
    path("companies/<int:pk>/update/", views.update_company, name="update_company"),
    path("companies/<int:pk>/contacts/", views.company_contacts, name="company_contacts"),
    path("deals/<int:pk>/contacts/create/", views.deal_contact_create, name="deal_contact_create"),
    path("deals/<int:pk>/contacts/<int:contact_id>/update/", views.deal_contact_update, name="deal_contact_update"),
    path("deals/<int:pk>/contacts/<int:contact_id>/delete/", views.deal_contact_delete, name="deal_contact_delete"),
 

]
