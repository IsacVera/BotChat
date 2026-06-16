from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Company, Document, Chunk, ChatSession, ChatTurn, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_companies')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'companies')
    filter_horizontal = ('companies', 'groups', 'user_permissions')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Company Association', {'fields': ('companies',)}),
    )
    
    def get_companies(self, obj):
        return ", ".join([c.name for c in obj.companies.all()])
    get_companies.short_description = 'Companies'


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'company', 'status', 'page_count', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('filename',)
    readonly_fields = ('created_at', 'storage_path')
    list_select_related = ('company',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('company', 'filename', 'storage_path')
        }),
        ('Processing Status', {
            'fields': ('status', 'page_count', 'error_message')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'company', 'page_from', 'page_to', 'word_count', 'created_at')
    list_filter = ('company', 'document')
    search_fields = ('text',)
    readonly_fields = ('created_at', 'word_count', 'text_preview')
    list_select_related = ('company', 'document')
    
    def word_count(self, obj):
        return len(obj.text.split()) if obj.text else 0
    word_count.short_description = 'Words'
    
    def text_preview(self, obj):
        return obj.text[:500] + '...' if len(obj.text) > 500 else obj.text
    text_preview.short_description = 'Text Preview'
    
    fieldsets = (
        ('References', {
            'fields': ('company', 'document')
        }),
        ('Page Range', {
            'fields': ('page_from', 'page_to')
        }),
        ('Content', {
            'fields': ('text_preview', 'word_count')
        }),
        ('Metadata', {
            'fields': ('version', 'created_at')
        }),
    )


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'user_id', 'created_at')
    list_filter = ('company',)
    search_fields = ('user_id',)
    readonly_fields = ('created_at',)
    list_select_related = ('company',)


@admin.register(ChatTurn)
class ChatTurnAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'user_question_preview', 'related', 'created_at')
    list_filter = ('related', 'session__company')
    search_fields = ('user_question', 'sanitized_query', 'reason')
    readonly_fields = ('created_at',)
    list_select_related = ('session', 'session__company')
    
    def user_question_preview(self, obj):
        return obj.user_question[:100] + '...' if len(obj.user_question) > 100 else obj.user_question
    user_question_preview.short_description = 'Question'
    
    fieldsets = (
        ('Session', {
            'fields': ('session',)
        }),
        ('Question', {
            'fields': ('user_question', 'sanitized_query')
        }),
        ('Classification', {
            'fields': ('related', 'policy_tags', 'reason')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
