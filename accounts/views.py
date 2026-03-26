from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, Address, VendorProfile, CustomerProfile
from .serializers import (
    UserSerializer, UserRegistrationSerializer,
    AddressSerializer, VendorProfileSerializer, CustomerProfileSerializer,
    VendorProfileUpdateSerializer, CustomerProfileUpdateSerializer,
    UserLoginSerializer, PasswordChangeSerializer,
)
from .permissions import IsVendor, IsSelf, IsAdminRole
import logging

logger = logging.getLogger(__name__)

def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ('register', 'login'):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'register':
            return UserRegistrationSerializer
        if self.action == 'login':
            return UserLoginSerializer
        if self.action == 'change_password':
            return PasswordChangeSerializer
        return UserSerializer

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'user': UserSerializer(user).data, 'tokens': get_tokens(user)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def login(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        user = authenticate(request, username=user_obj.username, password=password)
        if not user:
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'detail': 'Account is disabled.'}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {'user': UserSerializer(user).data, 'tokens': get_tokens(user)},
            status=status.HTTP_200_OK,
        )
        
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'detail': 'Refresh token required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            RefreshToken(refresh_token).blacklist()
            logger.info(f"Logout attempt for user: {request.user.email}")
            return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Error occurred while logging out.")
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        if request.method == 'GET':
            return Response(UserSerializer(request.user).data)
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='me/change-password')
    def change_password(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password updated.'}, status=status.HTTP_200_OK)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response({'detail': 'Default address updated.'})


class VendorProfileViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    serializer_class = VendorProfileSerializer

    def get_object(self):
        return self.request.user.vendor_profile

    @action(detail=False, methods=['get'])
    def me(self, request):
        return Response(VendorProfileSerializer(self.get_object()).data)

    @action(detail=False, methods=['patch'], url_path='me/update')
    def update_me(self, request):
        serializer = VendorProfileUpdateSerializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CustomerProfileViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        return self.request.user.customer_profile

    @action(detail=False, methods=['get'])
    def me(self, request):
        return Response(CustomerProfileSerializer(self.get_object()).data)

    @action(detail=False, methods=['patch'], url_path='me/update')
    def update_me(self, request):
        serializer = CustomerProfileUpdateSerializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)