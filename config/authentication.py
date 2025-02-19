import json

import jwt
import requests
from django.core.exceptions import ValidationError
from rest_framework.authentication import BasicAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from care.facility.models import Facility
from care.facility.models.asset import Asset
from care.users.models import User


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate_header(self, request):
        return ""

    def get_validated_token(self, raw_token):
        try:
            return super().get_validated_token(raw_token)
        except InvalidToken as e:
            raise InvalidToken({
                "detail": "Invalid Token, please relogin to continue",
                "messages" : e.detail.get("messages", [])
            }) from e


class CustomBasicAuthentication(BasicAuthentication):
    def authenticate_header(self, request):
        return ""


class MiddlewareAuthentication(JWTAuthentication):
    """
    An authentication plugin that authenticates requests through a JSON web
    token provided in a request header.
    """

    FACILITY_HEADER = "X-Facility-Id"

    def open_id_authenticate(self, url, token):
        public_key = requests.get(url)
        jwk = public_key.json()["keys"][0]
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        return jwt.decode(token, key=public_key, algorithms=["RS256"])

    def authenticate(self, request):
        raw_token = self.get_raw_token(self.get_header(request))
        if raw_token is None or self.FACILITY_HEADER not in request.headers:
            return None

        external_id = request.headers[self.FACILITY_HEADER]

        try:
            facility = Facility.objects.get(external_id=external_id)
        except (Facility.DoesNotExist, ValidationError) as e:
            raise InvalidToken({"detail": "Invalid Facility", "messages": []}) from e

        open_id_url = (
            facility.middleware_address
            or "http://localhost:8090" + "/.well-known/openid-configuration/"
        )

        validated_token = self.get_validated_token(open_id_url, raw_token)

        return self.get_user(validated_token, facility), validated_token

    def get_raw_token(self, header):
        """
        Extracts an invalidated JSON web token from the given "Authorization"
        header value.
        """
        parts = []
        try:
            parts = header.split()
            return parts[1]
        except (IndexError, TypeError) as e:
            if not parts or parts[0] not in (b"Middleware_Bearer",):
                return None
            raise InvalidToken(
                {
                    "detail": "Given token not valid for any token type",
                    "messages": [],
                }
            ) from e

    def get_validated_token(self, url, raw_token):
        """
        Validates an encoded JSON web token and returns a validated token
        wrapper object.
        """
        try:
            return self.open_id_authenticate(url, raw_token)
        except Exception as e:
            print(e)

        raise InvalidToken(
            {
                "detail": "Given token not valid for any token type",
                "messages": [],
            }
        )

    def get_user(self, validated_token, facility):
        """
        Attempts to find and return a user using the given validated token.
        """
        if "asset_id" not in validated_token:
            raise TokenError()

        try:
            asset_obj = Asset.objects.select_related("current_location__facility").get(
                external_id=validated_token["asset_id"]
            )
        except (Asset.DoesNotExist, ValidationError) as e:
            raise InvalidToken(
                {"detail": "Invalid Asset ID", "messages": [str(e)]}
            ) from e

        if asset_obj.current_location.facility != facility:
            raise InvalidToken({"detail": "Facility not connected to Asset"})

        # Create/Retrieve User and return them
        asset_user = User.objects.filter(asset=asset_obj).first()
        if not asset_user:
            password = User.objects.make_random_password()
            asset_user = User(
                username=f"asset{str(asset_obj.external_id)}",
                email="support@coronasafe.network",
                password=f"{password}123",
                gender=3,
                phone_number="919999999999",
                user_type=User.TYPE_VALUE_MAP["Staff"],
                verified=True,
                asset=asset_obj,
                age=10,
            )  # The 123 makes it inaccessible without hashing
            asset_user.save()
        return asset_user
