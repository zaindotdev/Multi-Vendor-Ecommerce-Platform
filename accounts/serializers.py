from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Address, VendorProfile, CustomerProfile


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id', 'address_line_1', 'address_line_2',
            'city', 'state', 'postal_code', 'country', 'is_default'
        ]

    def create(self, validated_data):
        user = self.context['request'].user
        return Address.objects.create(user=user, **validated_data)


class VendorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfile
        fields = [
            'id', 'company_name', 'company_slug', 'company_description',
            'logo_url', 'banner_url', 'commission_rate',
            'payout_threshold', 'is_approved'
        ]
        read_only_fields = ['commission_rate', 'payout_threshold', 'is_approved']


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ['id', 'phone_number']


class UserSerializer(serializers.ModelSerializer):
    vendor_profile = VendorProfileSerializer(read_only=True)
    customer_profile = CustomerProfileSerializer(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role',
            'is_active', 'date_joined',
            'vendor_profile', 'customer_profile', 'addresses'
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'role']

    def validate_role(self, value):
        # Prevent self-registration as admin
        if value == User.Role.ADMIN:
            raise serializers.ValidationError('Cannot register with admin role.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', User.Role.CUSTOMER),
        )


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})
        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()


class VendorProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfile
        fields = ['company_name', 'company_slug', 'company_description', 'logo_url', 'banner_url']


class CustomerProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ['phone_number']