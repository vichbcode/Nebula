"""Routes de l’application accounts."""

from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('welcome/', views.welcome_view, name='welcome'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('guest/', views.guest_login_view, name='guest'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/delete/', views.delete_account_view, name='delete_account'),
]