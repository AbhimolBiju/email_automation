from rest_framework import serializers
from django.contrib.auth.models import User
from .models import CustomUser, Profile, Role


class RegisterStep1Serializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    mobile = serializers.CharField()
    date_of_birth = serializers.DateField()
    gender = serializers.CharField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_mobile(self, value):
        if CustomUser.objects.filter(mobile=value).exists():
            raise serializers.ValidationError("Mobile already exists")
        return value





class RegisterStep2Serializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data




# ---------------- NEW: ROLE + PROFILE SERIALIZER ----------------
class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Role.objects.all()
    )

    class Meta:
        model = Profile
        fields = ['name', 'bio', 'profile_pic', 'role']


# ---------------- NEW: USER SERIALIZER (FOR UPDATE) ----------------
class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile']

    def update(self, instance, validated_data):
        request = self.context.get('request')   # ADD THIS
        profile_data = validated_data.pop('profile', None)

    # Update user fields
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.save()

        if profile_data:
            if request and request.user.is_staff:
                role_name = profile_data.get('role')
                role = Role.objects.get(name=role_name)
                instance.profile.role = role

    #  Update other profile fields (for all users)
            instance.profile.name = profile_data.get('name', instance.profile.name)
            instance.profile.bio = profile_data.get('bio', instance.profile.bio)
            instance.profile.save()

        return instance