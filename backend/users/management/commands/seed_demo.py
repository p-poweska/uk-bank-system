from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Account
from customers.models import Customer
from limits.models import AccountLimits, PaymentChannel
from notifications.models import Notification
from transactions.models import Transaction
from transfers.models import JuniorApproval, SavedRecipient, Transfer

try:
    from klik.models import KlikPayment
except Exception:  # pragma: no cover
    KlikPayment = None


DEMO_PASSWORD = "demo123"

PARENT_EMAIL = "demo.parent@ukbank.test"
JUNIOR_EMAIL = "demo.junior@ukbank.test"
RECEIVER_EMAIL = "demo.receiver@ukbank.test"
DEMO_EMAILS = [PARENT_EMAIL, JUNIOR_EMAIL, RECEIVER_EMAIL]

DEMO_ACCOUNT_NUMBERS = ["00000001", "00000002", "00000003"]
DEMO_IBANS = [
    "GB89LYOB10203000000001",
    "GB89LYOB10203000000002",
    "GB89LYOB10203000000003",
]


class Command(BaseCommand):
    help = (
        "Create clean demo data for the bank: users, one account per user, "
        "balances, history, recipients and KLIK limits. "
        "It does not create cards, pending junior approvals or pending KLIK payments."
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            self._purge_previous_demo_data()

            parent_user = self._create_user(PARENT_EMAIL, role="CUSTOMER")
            receiver_user = self._create_user(RECEIVER_EMAIL, role="CUSTOMER")
            junior_user = self._create_user(JUNIOR_EMAIL, role="JUNIOR")

            parent_customer = self._create_customer(
                user=parent_user,
                first_name="Mateusz",
                last_name="Demo Parent",
                date_of_birth=date(1998, 5, 12),
                phone="+447700900001",
                klik_phone_alias="+447700900001",
                country="United Kingdom",
                city="London",
                postcode="EC1A 1BB",
                street="Demo Street 1",
                parent_customer=None,
            )

            receiver_customer = self._create_customer(
                user=receiver_user,
                first_name="Adam",
                last_name="Receiver",
                date_of_birth=date(1996, 8, 22),
                phone="+447700900002",
                klik_phone_alias="+447700900002",
                country="United Kingdom",
                city="Manchester",
                postcode="M1 1AE",
                street="Receiver Road 12",
                parent_customer=None,
            )

            junior_customer = self._create_customer(
                user=junior_user,
                first_name="Oliwier",
                last_name="Demo Junior",
                date_of_birth=date(2015, 3, 10),
                phone="+447700900003",
                klik_phone_alias=None,
                country="United Kingdom",
                city="London",
                postcode="EC1A 1BB",
                street="Demo Street 1",
                parent_customer=parent_customer,
            )

            # Customer post_save signal creates random accounts automatically.
            # We remove them and create exact deterministic accounts below.
            Account.objects.filter(
                customer__in=[parent_customer, receiver_customer, junior_customer]
            ).delete()

            parent_account = self._create_account(
                customer=parent_customer,
                account_number="00000001",
                iban="GB89LYOB10203000000001",
                account_type="CURRENT",
                balance=Decimal("4872.50"),
            )

            receiver_account = self._create_account(
                customer=receiver_customer,
                account_number="00000002",
                iban="GB89LYOB10203000000002",
                account_type="CURRENT",
                balance=Decimal("1400.00"),
            )

            junior_account = self._create_account(
                customer=junior_customer,
                account_number="00000003",
                iban="GB89LYOB10203000000003",
                account_type="JUNIOR",
                balance=Decimal("150.00"),
            )

            self._seed_account_limits(parent_account)
            self._seed_account_limits(receiver_account)
            self._seed_account_limits(junior_account)

            self._seed_transactions(
                parent_user=parent_user,
                receiver_user=receiver_user,
                junior_user=junior_user,
                parent_account=parent_account,
                receiver_account=receiver_account,
                junior_account=junior_account,
            )
            self._seed_recipients(parent_user=parent_user, receiver_account=receiver_account)
            self._seed_notifications(parent_user=parent_user, junior_user=junior_user)

        self.stdout.write(self.style.SUCCESS("Clean demo data seeded successfully."))
        self.stdout.write("")
        self.stdout.write("Demo users:")
        self.stdout.write(f"  Parent:   {PARENT_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write(f"  Junior:   {JUNIOR_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write(f"  Receiver: {RECEIVER_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write("  Parent current: GB89LYOB10203000000001 balance £4872.50")
        self.stdout.write("  Local receiver: GB89LYOB10203000000002 balance £1400.00")
        self.stdout.write("  Junior account: GB89LYOB10203000000003 balance £150.00")
        self.stdout.write("")
        self.stdout.write("This seeder creates no cards, no pending junior approvals and no pending KLIK payments.")

    def _purge_previous_demo_data(self):
        User = get_user_model()

        demo_users = list(User.objects.filter(email__in=DEMO_EMAILS))
        demo_accounts = Account.objects.filter(
            customer__user__in=demo_users
        ) | Account.objects.filter(
            account_number__in=DEMO_ACCOUNT_NUMBERS
        ) | Account.objects.filter(
            iban__in=DEMO_IBANS
        )

        # Remove pending/demo objects explicitly first, so old seed artifacts never remain.
        JuniorApproval.objects.filter(parent_user__in=demo_users).delete()
        JuniorApproval.objects.filter(junior_user__in=demo_users).delete()
        JuniorApproval.objects.filter(from_account__in=demo_accounts).delete()

        Transfer.objects.filter(user__in=demo_users).delete()
        Transfer.objects.filter(from_account__in=demo_accounts).delete()
        SavedRecipient.objects.filter(user__in=demo_users).delete()
        Transaction.objects.filter(user__in=demo_users).delete()
        Transaction.objects.filter(account__in=demo_accounts).delete()
        Notification.objects.filter(user__in=demo_users).delete()

        if KlikPayment is not None:
            KlikPayment.objects.filter(user__in=demo_users).delete()
            KlikPayment.objects.filter(account__in=demo_accounts).delete()

        AccountLimits.objects.filter(account__in=demo_accounts).delete()

        # Delete users last. This cascades customers, accounts and any remaining demo records.
        User.objects.filter(email__in=DEMO_EMAILS).delete()

        # Remove possible orphaned demo customers/accounts from old broken seeders.
        Customer.objects.filter(phone__in=["+447700900001", "+447700900002", "+447700900003"]).delete()
        Account.objects.filter(account_number__in=DEMO_ACCOUNT_NUMBERS).delete()
        Account.objects.filter(iban__in=DEMO_IBANS).delete()

    def _create_user(self, email, role):
        User = get_user_model()
        user = User.objects.create(
            email=email,
            role=role,
            is_active=True,
            is_staff=False,
        )
        user.set_password(DEMO_PASSWORD)
        user.save(update_fields=["password"])
        return user

    def _create_customer(self, *, user, first_name, last_name, date_of_birth, phone,
                         klik_phone_alias, country, city, postcode, street, parent_customer):
        return Customer.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            phone=phone,
            klik_phone_alias=klik_phone_alias,
            country=country,
            city=city,
            postcode=postcode,
            street=street,
            parent_customer=parent_customer,
            kyc_verified=True,
        )

    def _create_account(self, *, customer, account_number, iban, account_type, balance):
        return Account.objects.create(
            customer=customer,
            account_number=account_number,
            sort_code="102030",
            iban=iban,
            currency="GBP",
            account_type=account_type,
            status="ACTIVE",
            balance=balance,
            available_balance=balance,
        )

    def _seed_account_limits(self, account):
        defaults = AccountLimits.defaults_for(account.account_type)
        for channel, values in defaults.items():
            if channel == PaymentChannel.CARD:
                continue

            AccountLimits.objects.create(
                account=account,
                card=None,
                channel=channel,
                per_transaction_limit=values["per_transaction_limit"],
                daily_limit=values["daily_limit"],
            )

    def _seed_transactions(self, *, parent_user, receiver_user, junior_user,
                           parent_account, receiver_account, junior_account):
        Transaction.objects.create(
            user=parent_user,
            account=parent_account,
            amount=Decimal("5000.00"),
            title="Initial demo deposit",
            balance_after=Decimal("5000.00"),
        )

        Transaction.objects.create(
            user=parent_user,
            account=parent_account,
            amount=Decimal("-75.00"),
            title="Groceries demo payment",
            balance_after=Decimal("4925.00"),
        )

        local_transfer = Transfer.objects.create(
            user=parent_user,
            from_account=parent_account,
            recipient_name="Adam Receiver",
            recipient_account=receiver_account.iban,
            amount=Decimal("52.50"),
            title="Demo internal transfer",
            routing_method="INTERNAL",
            status="COMPLETED",
        )

        Transaction.objects.create(
            user=parent_user,
            account=parent_account,
            transfer=local_transfer,
            amount=Decimal("-52.50"),
            title="Demo internal transfer to Adam Receiver",
            balance_after=Decimal("4872.50"),
        )

        Transaction.objects.create(
            user=receiver_user,
            account=receiver_account,
            amount=Decimal("1347.50"),
            title="Initial demo deposit",
            balance_after=Decimal("1347.50"),
        )

        Transaction.objects.create(
            user=receiver_user,
            account=receiver_account,
            transfer=local_transfer,
            amount=Decimal("52.50"),
            title="Demo internal transfer from Mateusz Demo Parent",
            balance_after=Decimal("1400.00"),
        )

        Transaction.objects.create(
            user=junior_user,
            account=junior_account,
            amount=Decimal("150.00"),
            title="Parent allowance demo deposit",
            balance_after=Decimal("150.00"),
        )

    def _seed_recipients(self, *, parent_user, receiver_account):
        recipients = [
            {
                "name": "Adam Receiver - local",
                "account": receiver_account.iban,
                "routing_method": "INTERNAL",
            },
            {
                "name": "Barclays test FPS",
                "account": "GB00BARC20000012345678",
                "routing_method": "FPS",
            },
            {
                "name": "HSBC test BACS",
                "account": "GB00HSBC40000012345678",
                "routing_method": "BACS",
            },
            {
                "name": "US SWIFT test",
                "account": "US123456789012345678901234",
                "routing_method": "SWIFT",
            },
        ]

        for data in recipients:
            SavedRecipient.objects.create(
                user=parent_user,
                name=data["name"],
                account=data["account"],
                routing_method=data["routing_method"],
            )

    def _seed_notifications(self, *, parent_user, junior_user):
        Notification.objects.create(
            user=parent_user,
            title="Demo account ready",
            body="Demo current account, local receiver, saved recipients and history are ready.",
            read=False,
        )
        Notification.objects.create(
            user=junior_user,
            title="Junior account ready",
            body="Demo junior account is linked to the parent profile and has test funds.",
            read=False,
        )
