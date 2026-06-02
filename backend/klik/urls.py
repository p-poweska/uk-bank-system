from django.urls import path

from .views import (
    AcceptKlikPaymentView,
    GenerateKlikCodeView,
    KlikAuthorizeWebhookView,
    PendingKlikPaymentsView,
    RejectKlikPaymentView,
)

urlpatterns = [
    path("klik/generate-code/", GenerateKlikCodeView.as_view(), name="klik-generate-code"),
    path("klik/webhook/authorize", KlikAuthorizeWebhookView.as_view(), name="klik-authorize-webhook"),
    path("klik/pending/", PendingKlikPaymentsView.as_view(), name="klik-pending"),
    path("klik/pending/<uuid:transaction_id>/accept/", AcceptKlikPaymentView.as_view(), name="klik-accept"),
    path("klik/pending/<uuid:transaction_id>/reject/", RejectKlikPaymentView.as_view(), name="klik-reject"),
]