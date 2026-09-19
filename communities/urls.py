"""Routes des communautés et de l’espace admin."""

from django.urls import path

from . import views

app_name = 'communities'

urlpatterns = [
    path('', views.index, name='index'),
    path('accueil/', views.home, name='home'),
    path('accueil/presence/', views.home_presence, name='home_presence'),

    path('communaute/<slug:slug>/', views.community_detail, name='detail'),
    path('communaute/<slug:slug>/rejoindre/', views.join_community, name='join'),
    path('communaute/<slug:slug>/quitter/', views.leave_community, name='leave'),
    path('communaute/<slug:slug>/message/', views.post_message, name='post_message'),
    path('communaute/<slug:slug>/messages/', views.chat_poll, name='chat_poll'),
    path('communaute/<slug:slug>/message/<int:pk>/supprimer/', views.delete_message, name='delete_message'),

    path('communaute/<slug:slug>/aide/', views.support_start, name='support_start'),
    path('communaute/<slug:slug>/aide/<int:thread_pk>/', views.support_thread, name='support_thread'),
    path('communaute/<slug:slug>/aide/<int:thread_pk>/repondre/', views.support_reply, name='support_reply'),
    path('communaute/<slug:slug>/aide/<int:thread_pk>/fermer/', views.support_close, name='support_close'),
    path('communaute/<slug:slug>/aide/<int:thread_pk>/supprimer/', views.support_delete, name='support_delete'),
    path('communaute/<slug:slug>/aide/<int:thread_pk>/messages/', views.support_poll, name='support_poll'),

    path('communaute/<slug:slug>/appel/lancer/', views.start_call, name='start_call'),
    path('communaute/<slug:slug>/appel/<int:call_pk>/terminer/', views.end_call, name='end_call'),
    path('communaute/<slug:slug>/appel/<int:call_pk>/jeton/', views.livekit_token, name='livekit_token'),
    path('communaute/<slug:slug>/appel/<int:call_pk>/signal/', views.call_signal, name='call_signal'),
    path('appel/turn/', views.turn_credentials, name='turn_credentials'),

    path('communaute/<slug:slug>/gestion/', views.manage_community, name='manage'),
    path('communaute/<slug:slug>/gestion/membre/', views.manage_add_member, name='manage_add_member'),
    path('communaute/<slug:slug>/gestion/membre/<int:user_id>/retirer/', views.manage_remove_member, name='manage_remove_member'),
    path('communaute/<slug:slug>/gestion/membre/<int:user_id>/bannir/', views.manage_ban_user, name='manage_ban_user'),
    path('communaute/<slug:slug>/gestion/membre/<int:user_id>/debloquer/', views.manage_unban_user, name='manage_unban_user'),
    path('communaute/<slug:slug>/gestion/invites/', views.manage_toggle_guests, name='manage_toggle_guests'),
    path('communaute/<slug:slug>/gestion/modifier/', views.manage_edit, name='manage_edit'),
    path('communaute/<slug:slug>/gestion/sous-admin/<int:user_id>/', views.manage_promote, name='manage_promote'),
    path('communaute/<slug:slug>/gestion/sous-admin/<int:user_id>/retirer/', views.manage_demote, name='manage_demote'),
    path('communaute/<slug:slug>/gestion/supprimer/', views.manage_delete, name='manage_delete'),

    # Espace admin du site
    path('espace-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('espace-admin/communautes/nouvelle/', views.admin_community_create, name='admin_community_create'),
    path('espace-admin/utilisateurs/', views.admin_users, name='admin_users'),
    path('espace-admin/utilisateurs/<int:user_id>/bannir/', views.admin_users_ban, name='admin_users_ban'),
    path('espace-admin/utilisateurs/<int:user_id>/debloquer/', views.admin_users_unban, name='admin_users_unban'),
    path('espace-admin/invites/', views.admin_guests, name='admin_guests'),
    path('espace-admin/invites/<int:user_id>/action/', views.admin_guests_action, name='admin_guests_action'),
    path('espace-admin/admins/', views.admin_admins, name='admin_admins'),
]