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
from limits.models import AccountLimits
from cards.serializers import CardSerializer
from transactions.models import Transaction
from notifications.utils import notify
from cards.models import Card

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
        account_id = request.data.get('account_id')
        channel = request.data.get('channel') 
        
        if not account_id or not channel:
            return Response({"error": "account_id and channel are required"}, status=status.HTTP_400_BAD_REQUEST)

        user_customer = request.user.customer
        account = get_object_or_404(Account, id=account_id)

        
        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        
        try:
            limit = account.limits.get(channel=channel)
        except AccountLimits.DoesNotExist:
            return Response({"error": f"Limit for channel {channel} not found"}, status=status.HTTP_404_NOT_FOUND)
        
        
        if 'per_transaction_limit' in request.data:
            limit.per_transaction_limit = request.data['per_transaction_limit']
        if 'daily_limit' in request.data:
            limit.daily_limit = request.data['daily_limit']

        limit.save()
        return Response({"message": "Limits updated successfully"}, status=status.HTTP_200_OK)