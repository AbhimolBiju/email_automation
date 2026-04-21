from django.shortcuts import render, get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterStep1Serializer,RegisterStep2Serializer,UserProfileSerializer
from .models import CustomUser,User
# Create your views here.
from rest_framework.response import Response
from rest_framework.decorators import api_view

@api_view(['GET'])
def test_api(request):
    return Response({"message":"API working"})

from rest_framework.permissions import AllowAny



@api_view(['POST'])
@permission_classes([AllowAny])
def register_step1(request):
    serializer = RegisterStep1Serializer(data=request.data)

    if serializer.is_valid():
        data = serializer.validated_data.copy()

    
        data['date_of_birth'] = data['date_of_birth'].isoformat()

        request.session['registration_data'] = data

        return Response({
            "message": "Step 1 completed. Proceed to set password."
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=400)




from datetime import date


@api_view(['POST'])
@permission_classes([AllowAny])
def register_step2(request):
    serializer = RegisterStep2Serializer(data=request.data)

    if serializer.is_valid():

        reg_data = request.session.get('registration_data')
        
        
        if not reg_data:
            return Response({"error": "Session expired. Start again."}, status=400)
        
        reg_data['date_of_birth'] = date.fromisoformat(reg_data['date_of_birth'])

        # Create User
        user = User.objects.create_user(
            username=reg_data['email'],
            email=reg_data['email'],
            password=serializer.validated_data['password'],
            first_name=reg_data['first_name'],
            last_name=reg_data['last_name']
        )

        # Create CustomUser
        CustomUser.objects.create(
            user=user,
            mobile=reg_data['mobile'],
            date_of_birth=reg_data['date_of_birth'],
            gender=reg_data['gender']
        )

        # Clear session
        del request.session['registration_data']

        return Response({
            "message": "User registered successfully"
        }, status=201)

    return Response(serializer.errors, status=400)





@api_view(['POST'])
@permission_classes([AllowAny]) 
def login_user(request):
    email = request.data.get('email')
    password = request.data.get('password')

    #using your EmailBackend
    user = authenticate(username=email, password=password)

    if user is not None:
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })

    return Response({
        "error": "Invalid credentials"
    }, status=status.HTTP_401_UNAUTHORIZED)
    


from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

@api_view(['POST'])
@permission_classes([IsAuthenticated])   
def logout_user(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logout successful"})
    except Exception as e:
        return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])  #Protected
def protected_view(request):
    return Response({
        "message": "Access granted",
        "user": request.user.username
    })



from rest_framework.permissions import IsAuthenticated

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    try:
        profile = request.user.user_profile
    except CustomUser.DoesNotExist:
        return Response({"error": "Profile not found"}, status=404)

    if request.method == 'GET':
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    if request.method in ['PUT', 'PATCH']:
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile updated successfully",
                "data": serializer.data
            })

        return Response(serializer.errors, status=400)