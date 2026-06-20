from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from accounts.models import Account
from .models import Transfer, SavedRecipient, JuniorApproval
from transactions.models import Transaction
from django.db.models import Q
from decimal import Decimal
from notifications.utils import notify
from . import swift_client

class TransferPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'


class TransferListView(APIView):
    """GET /api/transfers/ — all outgoing transfers for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Transfer.objects.filter(user=request.user).order_by('-created_at')
        paginator = TransferPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [
            {
                'id': t.id,
                'recipient_name': t.recipient_name,
                'recipient_account': t.recipient_account,
                'from_account_number': t.from_account.account_number,
                'amount': str(t.amount),
                'title': t.title,
                'routing_method': t.routing_method,
                'status': t.status,
                 # SWIFT details — null for normal FPS/BACS/CHAPS transfers
                'swift_uetr': t.swift_uetr,
                'sent_amount': str(t.sent_amount) if t.sent_amount is not None else None,
                'sent_currency': t.sent_currency,
                'debited_amount': str(t.debited_amount) if t.debited_amount is not None else None,
                'debited_currency': t.debited_currency,
                'exchange_rate': str(t.exchange_rate) if t.exchange_rate is not None else None,
                'fee_amount': str(t.fee_amount) if t.fee_amount is not None else None,
                'charge_bearer': t.charge_bearer,
                'created_at': t.created_at.isoformat(),
            }
            for t in page
        ]
        return paginator.get_paginated_response(data)


class SavedRecipientView(APIView):
    """GET/POST /api/recipients/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        recipients = SavedRecipient.objects.filter(user=request.user)
        data = [
            {
                'id': r.id,
                'name': r.name,
                'account': r.account,
                'routing_method': r.routing_method,
            }
            for r in recipients
        ]
        return Response(data)

    def post(self, request):
        name = request.data.get('name', '').strip()
        account = request.data.get('account', '').strip().replace(' ', '').upper()
        routing_method = request.data.get('routing_method', 'FPS')

        if not name or not account:
            return Response({'error': 'name and account are required'}, status=400)

        # Avoid exact duplicates for the same user
        if SavedRecipient.objects.filter(user=request.user, account=account).exists():
            return Response({'error': 'This recipient is already saved'}, status=400)

        r = SavedRecipient.objects.create(
            user=request.user, name=name, account=account, routing_method=routing_method
        )
        return Response({'id': r.id, 'name': r.name, 'account': r.account, 'routing_method': r.routing_method}, status=201)


class SavedRecipientDeleteView(APIView):
    """DELETE /api/recipients/{id}/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            r = SavedRecipient.objects.get(pk=pk, user=request.user)
            r.delete()
            return Response(status=204)
        except SavedRecipient.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)


class OwnTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            from_id = data.get('from_account')
            to_id = data.get('to_account')

            try:
                amount = Decimal(str(data.get('amount', '0')))
            except Exception:
                return Response({"error": "Invalid amount format"}, status=400)

            if amount <= 0:
                return Response({"error": "Amount must be greater than zero"}, status=400)

            try:
                source_acc = Account.objects.get(
                    Q(id=from_id) &
                    (Q(customer__user=request.user) | Q(customer__parent_customer__user=request.user))
                )
            except Account.DoesNotExist:
                return Response({"error": f"Source account {from_id} not found or unauthorized"}, status=404)

            try:
                target_acc = Account.objects.get(
                    Q(id=to_id) &
                    (Q(customer__user=request.user) | Q(customer__parent_customer__user=request.user))
                )
            except Account.DoesNotExist:
                return Response({"error": f"Target account {to_id} not found or unauthorized"}, status=404)

            if source_acc.available_balance < amount:
                return Response({"error": "Insufficient funds"}, status=400)

            if source_acc.account_type == "JUNIOR":
                return Response(
                    {"error": "Own transfers are not available for junior accounts."},
                    status=403,
                )

            if source_acc == target_acc:
                return Response({"error": "Cannot transfer to the same account"}, status=400)

            with transaction.atomic():
                source_acc.balance -= amount
                source_acc.available_balance -= amount
                target_acc.balance += amount
                target_acc.available_balance += amount
                source_acc.save()
                target_acc.save()

                transfer = Transfer.objects.create(
                    user=request.user,
                    from_account=source_acc,
                    recipient_name=f"Internal: {target_acc.account_type}",
                    recipient_account=target_acc.iban,
                    amount=amount,
                    title="Internal Transfer",
                    routing_method='INTERNAL',
                    status='COMPLETED'
                )

                Transaction.objects.create(
                    user=request.user, account=source_acc, transfer=transfer,
                    amount=-amount, title=f"To {target_acc.account_type}",
                    balance_after=source_acc.available_balance
                )
                Transaction.objects.create(
                    user=request.user, account=target_acc, transfer=transfer,
                    amount=amount, title=f"From {source_acc.account_type}",
                    balance_after=target_acc.available_balance
                )

                notify(request.user, 'Transfer sent',
                       f'You sent £{amount} to {target_acc.account_type} account.')
                notify(request.user, 'Transfer received',
                       f'£{amount} arrived in your {target_acc.account_type} account.')

            return Response({"status": "success"}, status=200)

        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
            return Response({"error": str(e)}, status=400)


class NationalTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            from_id = data.get('from_account')
            recipient_account = data.get('recipient_account', '').replace(' ', '')
            amount = Decimal(str(data.get('amount', '0')))

            source_acc = Account.objects.get(id=from_id, customer__user=request.user)

            if source_acc.account_type == 'JUNIOR':
                # Create a pending approval request for the parent instead of blocking
                try:
                    junior_customer = source_acc.customer
                    parent_customer = junior_customer.parent_customer
                    if not parent_customer or not parent_customer.user:
                        return Response({"error": "No parent account linked to approve transfers."}, status=400)
                    parent_user = parent_customer.user
                except Exception:
                    return Response({"error": "Could not locate parent account."}, status=400)

                approval = JuniorApproval.objects.create(
                    junior_user=request.user,
                    parent_user=parent_user,
                    from_account=source_acc,
                    recipient_name=data.get('recipient_name', ''),
                    recipient_account=recipient_account,
                    swift_bic=data.get('swift_bic') or None,
                    amount=amount,
                    title=data.get('title', 'Transfer'),
                    routing_method=data.get('routing_method', 'FPS'),
                )

                notify(parent_user, 'Transfer approval needed',
                       f'{junior_customer.first_name} wants to send £{amount} to {data.get("recipient_name", "")}. Review it in Payments.')
                notify(request.user, 'Transfer sent for approval',
                       f'Your transfer of £{amount} to {data.get("recipient_name", "")} is waiting for your parent to approve.')

                return Response({"status": "pending_approval", "approval_id": approval.id}, status=202)

            if source_acc.available_balance < amount:
                return Response({"error": "Insufficient funds"}, status=400)

            target_acc = Account.objects.filter(iban=recipient_account).first()

            if not target_acc:
                # Recipient is at another bank: route out through UK Payment
                # Systems (CHAPS / FPS / BACS) instead of failing.
                return self._route_external(request, source_acc, recipient_account, amount, data)

            with transaction.atomic():
                transfer = Transfer.objects.create(
                    user=request.user,
                    from_account=source_acc,
                    recipient_name=data.get('recipient_name', 'Lyo User'),
                    recipient_account=recipient_account,
                    amount=amount,
                    title=data.get('title', 'Transfer'),
                    routing_method=data.get('routing_method', 'FPS'),
                    status='COMPLETED'
                )

                source_acc.balance -= amount
                source_acc.available_balance -= amount

                target_acc.balance += amount
                target_acc.available_balance += amount
                source_acc.save()
                target_acc.save()

                Transaction.objects.create(
                    user=request.user, account=source_acc, transfer=transfer,
                    amount=-amount, title=transfer.title,
                    balance_after=source_acc.available_balance
                )

                recipient_user = target_acc.customer.user or target_acc.customer.parent_customer.user
                Transaction.objects.create(
                    user=recipient_user, account=target_acc, transfer=transfer,
                    amount=amount, title=transfer.title,
                    balance_after=target_acc.available_balance
                )

                notify(request.user, 'Transfer sent',
                       f'You sent £{amount} to {transfer.recipient_name}.')

                try:
                    if recipient_user:
                        notify(recipient_user, 'Money received',
                               f'You received £{amount} from a Lyo transfer.')
                except Exception:
                    pass

            return Response({"status": "success"}, status=200)

        except Account.DoesNotExist:
            return Response({"error": "Source account not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    def _route_external(self, request, source_acc, recipient_account, amount, data):
        """Send a transfer to an external UK bank via UKPS (CHAPS/FPS/BACS)."""
        from ukps import services as ukps
        from ukps.models import Scheme

        receiver_bic = (data.get('swift_bic') or '').strip().upper()
        if not receiver_bic:
            return Response(
                {"error": "Recipient bank BIC is required for transfers to other banks."},
                status=400,
            )

        scheme = (data.get('routing_method') or 'FPS').upper()

        if scheme == 'SWIFT':
            return self._route_swift(request, source_acc, recipient_account, amount, data)

        if scheme not in (Scheme.CHAPS, Scheme.FPS, Scheme.BACS):
            scheme = Scheme.FPS

        fps_max = Decimal(str(getattr(settings, 'UKPS_FPS_MAX_AMOUNT', '250000')))
        if scheme == Scheme.FPS and amount >= fps_max:
            return Response(
                {"error": f"FPS payments must be below £{fps_max:,.0f}. Use CHAPS for larger amounts."},
                status=400,
            )

        payment = ukps.send_payment(
            scheme=scheme,
            receiver_bic=receiver_bic,
            amount=amount,
            recipient_account=recipient_account,
            receiver_sort_code=data.get('recipient_sort_code', ''),
            reference=data.get('title', 'Transfer'),
        )

        if payment.status not in ukps.SUCCESS_STATUSES:
            reason = payment.reason_code or "the network declined the payment"
            if "opens at" in reason.lower() or "closed" in reason.lower():
                message = f"{scheme} is currently closed: {reason}."
            elif "unavailable" in reason.lower() or reason == "503":
                message = (
                    f"{scheme} could not reach the recipient bank. Check that the "
                    f"BIC '{receiver_bic}' belongs to a participating bank."
                )
            else:
                message = f"{scheme} payment was not accepted: {reason}."
            return Response(
                {
                    "error": message,
                    "scheme": scheme,
                    "ukps_status": payment.status,
                    "reason": payment.reason_code,
                },
                status=502,
            )

        # SETTLED moves immediately; QUEUED/RECEIVED settle later in the scheme.
        transfer_status = 'COMPLETED' if payment.status == 'SETTLED' else 'PENDING'

        with transaction.atomic():
            transfer = Transfer.objects.create(
                user=request.user,
                from_account=source_acc,
                recipient_name=data.get('recipient_name', 'External payee'),
                recipient_account=recipient_account,
                swift_bic=receiver_bic,
                amount=amount,
                title=data.get('title', 'Transfer'),
                routing_method=scheme,
                status=transfer_status,
            )

            source_acc.balance -= amount
            source_acc.available_balance -= amount
            source_acc.save()

            Transaction.objects.create(
                user=request.user, account=source_acc, transfer=transfer,
                amount=-amount, title=transfer.title,
                balance_after=source_acc.available_balance,
            )

            payment.transfer = transfer
            payment.save(update_fields=['transfer'])

            notify(request.user, 'Transfer sent',
                   f'You sent £{amount} to {transfer.recipient_name} via {scheme}.')

        return Response(
            {
                "status": "success",
                "scheme": scheme,
                "ukps_status": payment.status,
                "msg_id": payment.msg_id,
                "external_id": payment.external_id,
            },
            status=200,
        )

    def _route_swift(self, request, source_acc, recipient_account, amount, data):
        """
        Send an outgoing international payment through the external SWIFT middleware.

        Important:
        - `amount` is the amount sent to the recipient, e.g. 100 USD.
        - The sender account is debited in its own currency, usually GBP.
        - The bank applies a fixed FX rate and a local SWIFT fee.
        """
        receiver_bic = (data.get('swift_bic') or '').strip().upper()

        if not receiver_bic:
            return Response(
                {"error": "Recipient BIC/SWIFT code is required for SWIFT transfers."},
                status=400,
            )

        if receiver_bic == getattr(settings, 'SWIFT_BANK_BIC', 'UKBKGB01XXX'):
            return Response(
                {"error": "Use an internal transfer for accounts in this bank."},
                status=400,
            )

        source_currency = (source_acc.currency or 'GBP').upper()

        sent_currency = (
            data.get('transfer_currency')
            or swift_client.currency_for_bic(receiver_bic)
            or ''
        ).upper()

        charge_bearer = swift_client.normalize_charge_bearer(
            data.get('charge_bearer')
            or data.get('swift_charge_bearer')
            or 'SHA'
        )

        try:
            pricing = swift_client.calculate_pricing(
                sent_amount=amount,
                sent_currency=sent_currency,
                debited_currency=source_currency,
                charge_bearer=charge_bearer,
            )
        except swift_client.SwiftClientError as exc:
            return Response({"error": str(exc)}, status=400)

        if source_acc.available_balance < pricing.total_debit:
            return Response(
                {
                    "error": (
                        f"Insufficient funds. This SWIFT transfer requires "
                        f"{pricing.total_debit} {pricing.debited_currency} "
                        f"including a {pricing.fee_amount} {pricing.debited_currency} fee."
                    ),
                    "required_amount": str(pricing.total_debit),
                    "currency": pricing.debited_currency,
                },
                status=400,
            )

        sender_name = (
            f"{getattr(source_acc.customer, 'first_name', '')} "
            f"{getattr(source_acc.customer, 'last_name', '')}"
        ).strip()

        if not sender_name:
            sender_name = getattr(settings, 'SWIFT_BANK_NAME', 'Lyo Bank')

        try:
            submission = swift_client.send_payment(
                sender_name=sender_name,
                sender_account=source_acc.iban,
                receiver_name=data.get('recipient_name', 'External payee'),
                receiver_account=recipient_account,
                receiver_bic=receiver_bic,
                amount=pricing.sent_amount,
                currency=pricing.sent_currency,
                charge_bearer=pricing.charge_bearer,
                title=data.get('title', 'SWIFT transfer'),
            )
        except swift_client.SwiftClientError as exc:
            return Response(
                {
                    "error": f"SWIFT payment was not accepted: {str(exc)}",
                    "swift_status": exc.status_code,
                    "swift_payload": exc.payload,
                },
                status=502 if not exc.status_code or exc.status_code >= 500 else 400,
            )

        with transaction.atomic():
            locked_source = Account.objects.select_for_update().get(id=source_acc.id)

            if locked_source.available_balance < pricing.total_debit:
                return Response({"error": "Insufficient funds"}, status=400)

            transfer = Transfer.objects.create(
                user=request.user,
                from_account=locked_source,
                recipient_name=data.get('recipient_name', 'External payee'),
                recipient_account=recipient_account,
                swift_bic=receiver_bic,
                amount=pricing.sent_amount,
                title=data.get('title', 'SWIFT transfer'),
                routing_method='SWIFT',
                status='COMPLETED',

                swift_uetr=submission.uetr,
                swift_message_id=submission.message_id,

                sent_amount=pricing.sent_amount,
                sent_currency=pricing.sent_currency,

                debited_amount=pricing.total_debit,
                debited_currency=pricing.debited_currency,

                exchange_rate=pricing.exchange_rate,
                fee_amount=pricing.fee_amount,
                charge_bearer=pricing.charge_bearer,
            )

            locked_source.balance -= pricing.total_debit
            locked_source.available_balance -= pricing.total_debit
            locked_source.save(update_fields=['balance', 'available_balance'])

            Transaction.objects.create(
                user=request.user,
                account=locked_source,
                transfer=transfer,
                amount=-pricing.total_debit,
                title=(
                    f"SWIFT {pricing.sent_amount} {pricing.sent_currency} to "
                    f"{receiver_bic} — {transfer.title}"
                ),
                balance_after=locked_source.available_balance,
            )

            notify(
                request.user,
                'SWIFT transfer submitted',
                (
                    f"{pricing.sent_amount} {pricing.sent_currency} was submitted to "
                    f"{receiver_bic}. Debited {pricing.total_debit} {pricing.debited_currency} "
                    f"including fee {pricing.fee_amount} {pricing.debited_currency}."
                ),
            )

        return Response(
            {
                "status": "completed",
                "scheme": "SWIFT",
                "swift_status": submission.status,
                "auto_send_status": submission.auto_send_status,
                "uetr": submission.uetr,
                "message_id": submission.message_id,
                "route": submission.route,
                "receiver_bank": submission.receiver_bank,

                "sent_amount": str(pricing.sent_amount),
                "sent_currency": pricing.sent_currency,

                "debited_amount": str(pricing.total_debit),
                "debited_currency": pricing.debited_currency,

                "exchange_rate": str(pricing.exchange_rate),
                "fee_amount": str(pricing.fee_amount),
                "charge_bearer": pricing.charge_bearer,

                "swift_fee_breakdown": submission.fee_breakdown,
            },
            status=200,
        )


class JuniorApprovalListView(APIView):
    """GET /api/junior/approvals/ — pending approvals for the authenticated parent."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        approvals = JuniorApproval.objects.filter(
            parent_user=request.user,
            status='PENDING',
        )
        data = [
            {
                'id':               a.id,
                'junior_name':      f"{a.from_account.customer.first_name} {a.from_account.customer.last_name}",
                'from_account':     a.from_account.account_number,
                'recipient_name':   a.recipient_name,
                'recipient_account': a.recipient_account,
                'amount':           str(a.amount),
                'title':            a.title,
                'routing_method':   a.routing_method,
                'created_at':       a.created_at.isoformat(),
            }
            for a in approvals
        ]
        return Response(data)


class JuniorMyApprovalsView(APIView):
    """GET /api/junior/my-approvals/ — own pending approvals visible to the junior."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        approvals = JuniorApproval.objects.filter(
            junior_user=request.user,
            status='PENDING',
        )
        data = [
            {
                'id':               a.id,
                'recipient_name':   a.recipient_name,
                'recipient_account': a.recipient_account,
                'amount':           str(a.amount),
                'title':            a.title,
                'routing_method':   a.routing_method,
                'created_at':       a.created_at.isoformat(),
            }
            for a in approvals
        ]
        return Response(data)


class JuniorApprovalDecideView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        action = request.data.get('action')

        if action not in ('approve', 'reject'):
            return Response({'error': 'action must be "approve" or "reject"'}, status=400)

        try:
            approval = JuniorApproval.objects.get(
                pk=pk,
                parent_user=request.user,
                status='PENDING'
            )
        except JuniorApproval.DoesNotExist:
            return Response({'error': 'Approval not found or already decided.'}, status=404)

        if action == 'reject':
            approval.status = 'REJECTED'
            approval.decided_at = timezone.now()
            approval.save()

            notify(
                approval.junior_user,
                'Transfer rejected',
                f'Your transfer of £{approval.amount} to {approval.recipient_name} was rejected.'
            )

            return Response({'status': 'rejected'})

        with transaction.atomic():
            source_acc = Account.objects.select_for_update().get(id=approval.from_account_id)

            if source_acc.available_balance < approval.amount:
                return Response({'error': 'Junior account has insufficient funds.'}, status=400)

            target_acc = Account.objects.select_for_update().filter(
                iban=approval.recipient_account
            ).first()

            transfer = Transfer.objects.create(
                user=approval.junior_user,
                from_account=source_acc,
                recipient_name=approval.recipient_name,
                recipient_account=approval.recipient_account,
                swift_bic=approval.swift_bic,
                amount=approval.amount,
                title=approval.title,
                routing_method=approval.routing_method,
                status='COMPLETED',
            )

            source_acc.balance -= approval.amount
            source_acc.available_balance -= approval.amount
            source_acc.save()

            Transaction.objects.create(
                user=approval.junior_user,
                account=source_acc,
                transfer=transfer,
                amount=-approval.amount,
                title=approval.title,
                balance_after=source_acc.available_balance,
            )

            if target_acc:
                target_acc.balance += approval.amount
                target_acc.available_balance += approval.amount
                target_acc.save()

                recipient_user = target_acc.customer.user
                if not recipient_user and target_acc.customer.parent_customer:
                    recipient_user = target_acc.customer.parent_customer.user

                if recipient_user:
                    Transaction.objects.create(
                        user=recipient_user,
                        account=target_acc,
                        transfer=transfer,
                        amount=approval.amount,
                        title=approval.title,
                        balance_after=target_acc.available_balance,
                    )

                    notify(
                        recipient_user,
                        'Money received',
                        f'You received £{approval.amount} from {source_acc.customer.first_name}.'
                    )

            approval.status = 'APPROVED'
            approval.decided_at = timezone.now()
            approval.save()

            notify(
                approval.junior_user,
                'Transfer approved',
                f'Your transfer of £{approval.amount} to {approval.recipient_name} was approved and sent!'
            )

            notify(
                request.user,
                'Transfer approved',
                f'You approved £{approval.amount} transfer for {source_acc.customer.first_name}.'
            )

        return Response({'status': 'approved'})