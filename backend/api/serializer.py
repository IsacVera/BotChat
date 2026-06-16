from rest_framework import serializers
from core.models import Document, Company, User


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id', 'company', 'filename', 'storage_path',
            'page_count', 'status', 'error_message', 'created_at'
        ]


class AskSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    user_id = serializers.CharField(required=False, allow_blank=True, default="")
    question = serializers.CharField()
    session_id = serializers.CharField(required=False, allow_blank=True, default="")


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserSignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    company_name = serializers.CharField(max_length=200)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    
    def validate_company_name(self, value):
        if Company.objects.filter(name=value).exists():
            raise serializers.ValidationError("Company name already exists")
        return value


class UserLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # Can be username or email
    password = serializers.CharField(write_only=True)