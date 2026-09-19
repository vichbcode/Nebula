from django.contrib import admin

from communities.models import (Community, CommunityCall, Membership, Message,
                                SupportMessage, SupportThread)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_support', 'guests_allowed', 'member_count', 'created_at')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CommunityCall)
class CommunityCallAdmin(admin.ModelAdmin):
    list_display = ('community', 'started_by', 'call_type', 'started_at')


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display = ('user', 'admin', 'community', 'status', 'updated_at')
    list_filter = ('status', 'community')


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('thread', 'author', 'created_at')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'role', 'joined_at')
    list_filter = ('role', 'community')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('author', 'community', 'created_at')