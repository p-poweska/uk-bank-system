from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Account
from .serializers import AccountSerializer, DepositSerializer
from rest_framework import generics
from rest_framework.views import APIView
from django.db import transaction
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from rest_framework.response import Response
from customers.models import Customer
from django.db.models import Q, Prefetch
from datetime import datetime, date
import re
from limits.models import AccountLimits, PaymentChannel
from cards.serializers import CardSerializer
from transactions.models import Transaction
from notifications.utils import notify
from cards.models import Card
from decimal import Decimal

class MyAccountsListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated] 

    def get_queryset(self):
        user_customer = self.request.user.customer

        return (
            Account.objects
            .filter(
                Q(customer=user_customer)
                |
                Q(
                    customer__parent_customer=
                        user_customer
                )
            )
            .prefetch_related(
                Prefetch(
                    "cards",
                    queryset=Card.objects.filter(
                        is_archived=False
                    ),
                    to_attr="visible_cards",
                ),
                "limits",
            )
            .order_by("created_at")
        )

class CreateJuniorAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        parent_customer = request.user.customer
        
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        dob = request.data.get('date_of_birth')

        if not first_name or not last_name or not dob:
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        name_regex = r'^[A-Za-zżźćńółęąśŻŹĆŃÓŁĘĄŚ\s-]+$'
        if len(first_name) < 2 or len(last_name) < 2:
            return Response({"error": "Names must be at least 2 characters long."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not re.match(name_regex, first_name) or not re.match(name_regex, last_name):
            return Response({"error": "Names can only contain letters, spaces, or hyphens."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
            today = date.today()
            age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))

            if age < 7 or age > 13:
                return Response(
                    {"error": "Junior account is strictly for children between 7 and 13 years old."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        junior_customer = Customer.objects.create(
            user=None,
            first_name=first_name.title(),
            last_name=last_name.title(),
            date_of_birth=dob_date,
            phone=parent_customer.phone,
            country=parent_customer.country,
            city=parent_customer.city,
            postcode=parent_customer.postcode,
            street=parent_customer.street,
            parent_customer=parent_customer,
            kyc_verified=True
        )

        notify(request.user, 'Junior account created',
               f'Junior account for {first_name.title()} {last_name.title()} has been created successfully.')

        return Response({"message": "Junior account created", "customer_id": junior_customer.id}, status=status.HTTP_201_CREATED)


class AccountDepositView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        account_id = request.data.get('account_id')
        
        if not account_id:
            return Response({"error": "account_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        account = get_object_or_404(
            Account, 
            id=account_id, 
            customer__user=request.user
        )
        
        serializer = DepositSerializer(data=request.data)
        
        if serializer.is_valid():
            amount_to_add = serializer.validated_data['amount']

            account.balance += amount_to_add
            account.available_balance += amount_to_add
            account.save()

            Transaction.objects.create(
                user=request.user,
                account=account,
                amount=amount_to_add,
                title='Add money',
                balance_after=account.available_balance,
            )

            return Response({
                "message": "Deposit successful",
                "new_balance": str(account.balance)
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateAccountLimitsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        account_id = request.data.get("account_id")
        card_id = request.data.get("card_id")
        channel = request.data.get("channel")

        if not channel:
            return Response(
                {"error": "channel is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_channels = [choice[0] for choice in PaymentChannel.choices]

        if channel not in valid_channels:
            return Response(
                {"error": f"Invalid limit channel: {channel}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_customer = request.user.customer

        if channel == PaymentChannel.CARD:
            if not card_id:
                return Response(
                    {"error": "card_id is required for card limits"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            card = get_object_or_404(
                Card.objects.select_related("account__customer"),
                id=card_id,
                is_archived=False,
            )

            account = card.account

            if (
                account.customer != user_customer
                and account.customer.parent_customer != user_customer
            ):
                return Response(
                    {"error": "Unauthorized"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            defaults = AccountLimits.card_defaults_for(
                account.account_type,
                card.card_type,
            )

            limit, _ = AccountLimits.objects.get_or_create(
                account=account,
                card=card,
                channel=PaymentChannel.CARD,
                defaults=defaults,
            )

        else:
            if channel not in [PaymentChannel.BLIK, PaymentChannel.BLIK_PHONE]:
                return Response(
                    {"error": "Only card and KLIK limits are supported"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not account_id:
                return Response(
                    {"error": "account_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            account = get_object_or_404(Account, id=account_id)

            if (
                account.customer != user_customer
                and account.customer.parent_customer != user_customer
            ):
                return Response(
                    {"error": "Unauthorized"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            defaults = AccountLimits.defaults_for(account.account_type).get(
                channel,
                {
                    "per_transaction_limit": Decimal("0.00"),
                    "daily_limit": Decimal("0.00"),
                },
            )

            limit, _ = AccountLimits.objects.get_or_create(
                account=account,
                card=None,
                channel=channel,
                defaults=defaults,
            )

        try:
            per_transaction_limit = Decimal(
                str(request.data.get("per_transaction_limit", limit.per_transaction_limit))
            )

            daily_limit = Decimal(
                str(request.data.get("daily_limit", limit.daily_limit))
            )

        except Exception:
            return Response(
                {"error": "Invalid limit value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if per_transaction_limit < 0 or daily_limit < 0:
            return Response(
                {"error": "Limits cannot be negative"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if per_transaction_limit > daily_limit:
            return Response(
                {"error": "Per transaction limit cannot be higher than daily limit"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit.per_transaction_limit = per_transaction_limit
        limit.daily_limit = daily_limit
        limit.save(
            update_fields=[
                "per_transaction_limit",
                "daily_limit",
                "updated_at",
            ],
        )

        return Response(
            {
                "message": "Limits updated successfully",
                "channel": limit.channel,
                "account_id": str(limit.account_id),
                "card_id": str(limit.card_id) if limit.card_id else None,
                "per_transaction_limit": str(limit.per_transaction_limit),
                "daily_limit": str(limit.daily_limit),
            },
            status=status.HTTP_200_OK,
        )