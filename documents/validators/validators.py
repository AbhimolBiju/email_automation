from rest_framework import serializers

def validate_file_size(value):
    if value.size > 2 * 1024 * 1024:  # 2MB
        raise serializers.ValidationError("File size should not exceed 2MB")
    return value