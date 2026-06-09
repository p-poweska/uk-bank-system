from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q
from accounts.models import Account
from .models import Transaction
from .serializers import TransactionSerializer
from datetime import date

class TransactionPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50

class AccountTransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        user_customer = request.user.customer
        account = get_object_or_404(Account, id=account_id)

        if account.customer != user_customer and account.customer.parent_customer != user_customer:
            return Response({"error": "Unauthorized"}, status=403)

        qs = (
            account.history
            .select_related(
                "transfer",
                "card_payment_capture__card",
            )
            .all()
            .order_by("-created_at")
        )

        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')
        tx_type = request.query_params.get('type')

        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        if tx_type == 'CREDIT':
            qs = qs.filter(amount__gt=0)
        elif tx_type == 'DEBIT':
            qs = qs.filter(amount__lt=0)

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(transfer__recipient_name__icontains=search)
                | Q(
                    card_payment_capture__merchant_id__icontains=
                    search
                )
            )

        paginator = TransactionPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = TransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AnalyticsSummaryView(APIView):
    """GET /api/analytics/summary/?months=6"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            months = max(1, min(24, int(request.query_params.get('months', 6))))
        except ValueError:
            months = 6

        # Build list of first-of-month dates going back `months` months
        today = date.today()
        month_starts = []
        for i in range(months - 1, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            month_starts.append(date(y, m, 1))

        start_date = month_starts[0]

        # All accounts this user owns (including junior children)
        user_customer = request.user.customer
        accounts = Account.objects.filter(
            Q(customer=user_customer) | Q(customer__parent_customer=user_customer)
        )

        txs = Transaction.objects.filter(
            account__in=accounts,
            created_at__date__gte=start_date,
        ).select_related('transfer')

        # --- Monthly income vs expenses ---
        monthly_map = {
            ms.strftime('%b %Y'): {'income': 0.0, 'expenses': 0.0}
            for ms in month_starts
        }

        # --- Category breakdown (absolute GBP values) ---
        breakdown = {'Deposits': 0.0, 'Card Top-up': 0.0, 'Transfers In': 0.0, 'Transfers Out': 0.0}

        for tx in txs:
            amt = float(tx.amount)
            key = tx.created_at.strftime('%b %Y')
            if key not in monthly_map:
                continue

            title_lower = tx.title.lower()

            if amt > 0:
                monthly_map[key]['income'] += amt
                if 'add money' in title_lower:
                    breakdown['Deposits'] += amt
                else:
                    breakdown['Transfers In'] += amt
            else:
                monthly_map[key]['expenses'] += abs(amt)
                if 'top-up' in title_lower:
                    breakdown['Card Top-up'] += abs(amt)
                else:
                    breakdown['Transfers Out'] += abs(amt)

        monthly = [
            {'month': k, 'income': round(v['income'], 2), 'expenses': round(v['expenses'], 2)}
            for k, v in monthly_map.items()
        ]

        breakdown_list = [
            {'name': k, 'value': round(v, 2)}
            for k, v in breakdown.items()
            if v > 0
        ]

        total_income = sum(m['income'] for m in monthly)
        total_expenses = sum(m['expenses'] for m in monthly)

        return Response({
            'monthly': monthly,
            'breakdown': breakdown_list,
            'totals': {
                'income': round(total_income, 2),
                'expenses': round(total_expenses, 2),
                'net': round(total_income - total_expenses, 2),
            }
        })
