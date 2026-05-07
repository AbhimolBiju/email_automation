# from rest_framework import serializers
# from django.contrib.auth.models import User
# from .models import CustomUser


# class RegisterStep1Serializer(serializers.Serializer):
#     email = serializers.EmailField()
#     first_name = serializers.CharField()
#     last_name = serializers.CharField()
#     mobile = serializers.CharField()
#     date_of_birth = serializers.DateField()
#     gender = serializers.CharField()

#     def validate_email(self, value):
#         if User.objects.filter(email=value).exists():
#             raise serializers.ValidationError("Email already exists")
#         return value

#     def validate_mobile(self, value):
#         if CustomUser.objects.filter(mobile=value).exists():
#             raise serializers.ValidationError("Mobile already exists")
#         return value





# class RegisterStep2Serializer(serializers.Serializer):
#     password = serializers.CharField(write_only=True)
#     confirm_password = serializers.CharField(write_only=True)

#     def validate(self, data):
#         if data['password'] != data['confirm_password']:
#             raise serializers.ValidationError("Passwords do not match")
#         return data






# class UserProfileSerializer(serializers.ModelSerializer):
#     email = serializers.EmailField(source='user.email', read_only=True)
#     first_name = serializers.CharField(source='user.first_name')
#     last_name = serializers.CharField(source='user.last_name')

#     role = serializers.CharField(read_only=True)  # 👈 IMPORTANT

#     class Meta:
#         model = CustomUser
#         fields = [
#             'email',
#             'first_name',
#             'last_name',
#             'mobile',
#             'date_of_birth',
#             'gender',
#             'address',
#             'city',
#             'zip_code',
#             'country',
#             'role'  # visible but not editable
#         ]

#     def update(self, instance, validated_data):
#         user_data = validated_data.pop('user', {})

#         # Update User model fields
#         user = instance.user
#         user.first_name = user_data.get('first_name', user.first_name)
#         user.last_name = user_data.get('last_name', user.last_name)
#         user.save()

#         # Update CustomUser fields
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)

#         instance.save()
#         return instance
# from django.contrib.auth.models import User
# from rest_framework import serializers
# from .models import CustomUser


# class UserCreateSerializer(serializers.Serializer):
#     first_name = serializers.CharField()
#     last_name = serializers.CharField()
#     email = serializers.EmailField()
#     mobile = serializers.CharField()
#     gender = serializers.CharField(required=False, allow_blank=True)
#     role = serializers.ChoiceField(choices=CustomUser.ROLE_CHOICES)

#     def create(self, validated_data):
#         # Extract custom fields
#         mobile = validated_data.pop("mobile")
#         gender = validated_data.pop("gender", None)
#         role = validated_data.pop("role")

#         # Create Django User (NO PASSWORD)
#         user = User.objects.create(
#             username=validated_data["email"],  # use email as username
#             email=validated_data["email"],
#             first_name=validated_data["first_name"],
#             last_name=validated_data["last_name"],
#         )

#         # Disable password login for now
#         user.set_unusable_password()
#         user.save()

#         # Create CustomUser profile
#         CustomUser.objects.create(
#             user=user,
#             mobile=mobile,
#             gender=gender,
#             role=role
#         )

#         return user
    
# class UserListSerializer(serializers.ModelSerializer):
#     first_name = serializers.CharField(source='user.first_name')
#     last_name = serializers.CharField(source='user.last_name')
#     email = serializers.EmailField(source='user.email')

#     class Meta:
#         model = CustomUser
#         fields = [
#             'id',
#             'first_name',
#             'last_name',
#             'email',
#             'mobile',
#             'role',
#             'gender'
#         ]


# from rest_framework import serializers

# class UserRoleUpdateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CustomUser
#         fields = ['role']

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import CustomUser


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






class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')

    role = serializers.CharField(read_only=True)  # 👈 IMPORTANT

    class Meta:
        model = CustomUser
        fields = [
            'email',
            'first_name',
            'last_name',
            'mobile',
            'date_of_birth',
            'gender',
            'address',
            'city',
            'zip_code',
            'country',
            'role'  # visible but not editable
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})

        # Update User model fields
        user = instance.user
        user.first_name = user_data.get('first_name', user.first_name)
        user.last_name = user_data.get('last_name', user.last_name)
        user.save()

        # Update CustomUser fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import CustomUser


class UserCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    mobile = serializers.CharField()
    gender = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=CustomUser.ROLE_CHOICES)

    def create(self, validated_data):
        # Extract custom fields
        mobile = validated_data.pop("mobile")
        gender = validated_data.pop("gender", None)
        role = validated_data.pop("role")

        # Create Django User (NO PASSWORD)
        user = User.objects.create(
            username=validated_data["email"],  # use email as username
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
        )

        # Disable password login for now
        user.set_unusable_password()
        user.save()

        # Create CustomUser profile
        CustomUser.objects.create(
            user=user,
            mobile=mobile,
            gender=gender,
            role=role
        )

        return user

# api/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import CustomUser


class UserListSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'mobile',
            'role',
            'gender'
        ]


from rest_framework import serializers

class UserRoleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['role']

class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    mobile = serializers.CharField(required=False)
    gender = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        required=False
    )

    def validate_email(self, value):
        instance = self.instance

        # Check username already exists in another user
        if User.objects.exclude(id=instance.user.id).filter(
            username=value
        ).exists():
            raise serializers.ValidationError(
                "Email already exists"
            )

        return value

    def update(self, instance, validated_data):

        user = instance.user

        user.first_name = validated_data.get(
            "first_name",
            user.first_name
        )

        user.last_name = validated_data.get(
            "last_name",
            user.last_name
        )

        # Update email + username
        if "email" in validated_data:
            user.email = validated_data["email"]
            user.username = validated_data["email"]

        user.save()

        # CustomUser fields
        instance.mobile = validated_data.get(
            "mobile",
            instance.mobile
        )

        instance.gender = validated_data.get(
            "gender",
            instance.gender
        )

        instance.role = validated_data.get(
            "role",
            instance.role
        )

        instance.save()

        return instance
    
# serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User

from .models import CustomUser


class ProfileSerializer(serializers.ModelSerializer):

    first_name = serializers.CharField(
        source='user.first_name',
        required=False
    )

    last_name = serializers.CharField(
        source='user.last_name',
        required=False
    )

    email = serializers.EmailField(
        source='user.email',
        required=False
    )

    date_joined = serializers.DateTimeField(
        source='user.date_joined',
        read_only=True
    )

    class Meta:
        model = CustomUser

        fields = [
            'id',

            'first_name',
            'last_name',
            'email',
            'date_joined',

            'mobile',
            'date_of_birth',
            'gender',
            'address',
            'city',
            'zip_code',
            'country',
            'emirates_of_visa',
            'insurance_company',
            'currently_insured',
            'salary_band',
            'profile_pic',
            'role',
            'modified_on',
        ]

        read_only_fields = [
            'role',
            'modified_on',
            'date_joined'
        ]

    def update(self, instance, validated_data):

        user_data = validated_data.pop('user', {})

        # Update Django User table
        user = instance.user

        user.first_name = user_data.get(
            'first_name',
            user.first_name
        )

        user.last_name = user_data.get(
            'last_name',
            user.last_name
        )

        user.email = user_data.get(
            'email',
            user.email
        )

        user.save()

        # Update CustomUser table
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance