from django.urls import path
from . import views

urlpatterns = [
    # Documents
    path('docs/upload', views.docs_upload, name='docs-upload'),
    path('docs/load-default', views.docs_load_default, name='docs-load-default'),
    path('docs', views.docs_list, name='docs-list'),
    path('docs/<int:doc_id>', views.docs_detail, name='docs-detail'),

    # Chat
    path('chat/ask', views.chat_ask, name='chat-ask'),
    path('chat/policy-check', views.chat_policy_check, name='chat-policy-check'),

    # Company & User
    path('companies/', views.company_create, name='company-create'),
    path('users/signup/', views.user_signup, name='user-signup'),
    path('users/login/', views.user_login, name='user-login'),
]