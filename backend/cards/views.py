import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from accounts.models import Account
from .models import Card
from decimal import Decimal
from django.db import transaction
from transactions.models import Transaction
from notifications.utils import notify

class CreateCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_id = request.data.get('account_id')
        card_type = request.data.get('card_type', 'VIRTUAL')
        account = get_object_or_404(Account, id=account_id)

        
        user_customer = request.user.customer
        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        
        if account.account_type == 'JUNIOR':
            if account.cards.filter(card_type='PREPAID').count() >= 1:
                return Response({"error": "Junior can only have 1 Prepaid card."}, status=status.HTTP_400_BAD_REQUEST)
            card_type = 'PREPAID'
        else:
            
            current_type_count = account.cards.filter(card_type=card_type).count()
            if current_type_count >= 2:
                return Response({"error": f"You can only have 2 {card_type} cards."}, status=status.HTTP_400_BAD_REQUEST)

        # MOCKOWANIE DANYCH (Zastąpione przez API Providera w przyszłości)
        last_4 = str(random.randint(1000, 9999))
        full_num = f"444455556666{last_4}"
        cvv = str(random.randint(100, 999))
        pin = str(random.randint(1000, 9999))
        
        cardholder = f"{account.customer.first_name} {account.customer.last_name}".upper()

        card = Card.objects.create(
            account=account,
            card_type=card_type,
            cardholder_name=cardholder,
            masked_number=f"**** **** **** {last_4}",
            full_number=full_num,
            cvv=cvv,
            pin=pin,
            expiry_date="12/28",
            status=Card.CardStatus.ACTIVE
        )

        return Response({"message": "Card created", "id": card.id}, status=status.HTTP_201_CREATED)

class CardManageView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        card_id = request.data.get('card_id')
        card = get_object_or_404(Card, id=card_id)
        
        
        user_customer = request.user.customer
        if card.account.customer != user_customer and card.account.customer.parent_customer != user_customer:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        if new_status in Card.CardStatus.values:
            card.status = new_status
            card.save()
            return Response({"status": card.status})
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        card_id = request.data.get('card_id')
        card = get_object_or_404(Card, id=card_id)
        
        user_customer = request.user.customer
        if card.account.customer != user_customer and card.account.customer.parent_customer != user_customer:
            return Response(status=status.HTTP_403_FORBIDDEN)

        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class TopUpPrepaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        card_id = request.data.get('card_id')
        try:
            amount = Decimal(str(request.data.get('amount', '0')))
        except Exception:
            return Response({"error": "Invalid amount"}, status=400)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero"}, status=400)

        card = get_object_or_404(Card, id=card_id)
        account = card.account

        user_customer = request.user.customer
        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response({"error": "Unauthorized"}, status=403)

        if card.card_type != 'PREPAID':
            return Response({"error": "Only prepaid cards can be topped up"}, status=400)

        if account.available_balance < amount:
            return Response({"error": "Insufficient funds on the main account"}, status=400)

        with transaction.atomic():
            
            account.balance -= amount
            account.available_balance -= amount
            card.prepaid_balance += amount
            account.save()
            card.save()

            Transaction.objects.create(
                user=request.user,
                account=account,
                amount=-amount,
                title=f"Top-up Prepaid Card {card.masked_number}",
                balance_after=account.available_balance
            )

            notify(request.user, 'Card topped up',
                   f'Your prepaid card {card.masked_number} has been topped up with £{amount}.')

        return Response({
            "message": "Card topped up successfully", 
            "new_prepaid_balance": card.prepaid_balance,
            "new_account_balance": account.available_balance
        }, status=200)