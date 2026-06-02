from django.urls import path

from .views import (
    AcceptKlikPaymentView,
    GenerateKlikCodeView,
    KlikAuthorizeWebhookView,
    PendingKlikPaymentsView,
    RejectKlikPaymentView,
    RegisterKlikAliasView,
    RemoveKlikAliasView,
    MyKlikAliasView,
    SendKlikP2PView,
)

urlpatterns = [
    path("klik/generate-code/", GenerateKlikCodeView.as_view(), name="klik-generate-code"),
    path("klik/webhook/authorize", KlikAuthorizeWebhookView.as_view(), name="klik-authorize-webhook"),
    path("klik/pending/", PendingKlikPaymentsView.as_view(), name="klik-pending"),
    path("klik/pending/<uuid:transaction_id>/accept/", AcceptKlikPaymentView.as_view(), name="klik-accept"),
    path("klik/pending/<uuid:transaction_id>/reject/", RejectKlikPaymentView.as_view(), name="klik-reject"),
    path("klik/alias/register/", RegisterKlikAliasView.as_view(), name="klik-alias-register"),
    path("klik/alias/remove/", RemoveKlikAliasView.as_view(), name="klik-alias-remove"),
    path("klik/alias/", MyKlikAliasView.as_view(), name="klik-alias"),
    path("klik/p2p/send/", SendKlikP2PView.as_view(), name="klik-p2p-send"),
]