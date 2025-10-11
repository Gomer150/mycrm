from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('deals/', views.deals_list, name='deals_list'),
    path('actions/', views.actions_list, name='actions_list'),
    path('clients/', views.clients_list, name='clients_list'),
    path('contacts/', views.contacts_list, name='contacts_list'),

    path('deals/<int:pk>/', views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/edit/', views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/upload/', views.upload_document, name='upload_document'),

    path('deals/<int:pk>/actions/create/', views.deal_action_create, name='deal_action_create'),
    path('deals/<int:pk>/actions/<int:action_id>/update/', views.deal_action_update, name='deal_action_update'),
    path('deals/<int:pk>/actions/<int:action_id>/delete/', views.deal_action_delete, name='deal_action_delete'),

    path('document/<int:doc_id>/download/', views.download_document, name='download_document'),
    path('document/<int:doc_id>/delete/', views.delete_document, name='delete_document'),

    path('deals/create/', views.create_deal, name='create_deal'),
    path('companies/create/', views.create_company, name='create_company'),
    path('companies/<int:pk>/update/', views.update_company, name='update_company'),
    path('companies/<int:pk>/contacts/', views.company_contacts, name='company_contacts'),

    path('deals/<int:pk>/contacts/create/', views.deal_contact_create, name='deal_contact_create'),
    path('deals/<int:pk>/contacts/<int:contact_id>/update/', views.deal_contact_update, name='deal_contact_update'),
    path('deals/<int:pk>/contacts/<int:contact_id>/delete/', views.deal_contact_delete, name='deal_contact_delete'),
]
