from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from deals import views as deals_views

urlpatterns = [
#    path('admin/', admin.site.urls),
#    path('accounts/login/', auth_views.LoginView.as_view(template_name="deals/login.html"), name='login'),
    path('', deals_views.index, name='home'),  # главная страница
    path('deals/', deals_views.deals_list, name='deals_list'),
    path('deals/<int:pk>/edit/', deals_views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/', deals_views.deal_detail, name='deal_detail'),
    path('deals/<int:pk>/upload/', deals_views.upload_document, name='upload_document'),
    path('document/<int:doc_id>/download/', deals_views.download_document, name='download_document'),

#    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
]
