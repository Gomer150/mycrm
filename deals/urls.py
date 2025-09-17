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
    path('document/<int:doc_id>/download/', deals_views.download_document, name='download_document'),
    path("deals/create/", views.create_deal, name="create_deal"),
    path("document/<int:doc_id>/delete/", views.delete_document, name="delete_document"),
    path("companies/create/", views.create_company, name="create_company"),
 

]
