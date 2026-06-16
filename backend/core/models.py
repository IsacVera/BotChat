from django.db import models
from django.contrib.auth.models import AbstractUser


class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Custom user model that can belong to multiple companies"""
    companies = models.ManyToManyField(Company, related_name='users', blank=True)
    
    def __str__(self):
        return self.username


class Document(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documents')
    filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500)
    page_count = models.IntegerField(default=0)
    status = models.CharField(max_length=30, default='uploaded')  # uploaded|processing|ready|error
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company.name}:{self.filename}"


class Chunk(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='chunks')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    page_from = models.IntegerField()
    page_to = models.IntegerField()
    text = models.TextField()
    # store embedding as bytes or JSON until pgvector is configured
    embedding = models.BinaryField(null=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class ChatSession(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user_id = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)


class ChatTurn(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='turns')
    user_question = models.TextField()
    sanitized_query = models.TextField(blank=True, default='')
    related = models.BooleanField(null=True)
    policy_tags = models.JSONField(default=list)
    reason = models.CharField(max_length=300, blank=True, default='')

    answer_json = models.JSONField(null=True)
    topk_chunks = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
