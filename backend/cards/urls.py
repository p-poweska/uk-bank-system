from django.urls import path
from .views import (
    CardManageView,
    CreateCardView,
    SyncCardStatusView,
    TopUpPrepaidView,
)

urlpatterns = [
    path('cards/create/', CreateCardView.as_view(), name='create-card'),
    path('cards/manage/', CardManageView.as_view(), name='manage-card'),
    path('cards/topup/', TopUpPrepaidView.as_view(), name='topup-card'),
    path('cards/sync-status/', SyncCardStatusView.as_view(), name='sync-card-status'),
]