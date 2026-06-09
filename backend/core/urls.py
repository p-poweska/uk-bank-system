"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import RegisterView, CustomLoginView, CreateJuniorUserView, ChangePasswordView, ChangeEmailView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from cards.views import CardPaymentCaptureView

urlpatterns = [
    path('admin/', admin.site.urls),


    path('api/auth/login/', CustomLoginView.as_view(), name='auth_login'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/register/', RegisterView.as_view(), name='auth_register'),
    path('api/auth/junior/setup/', CreateJuniorUserView.as_view(), name='junior_setup'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('api/auth/change-email/', ChangeEmailView.as_view(), name='change_email'),
    path("capture",CardPaymentCaptureView.as_view(),name="card-payment-capture"),

    # swager

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('api/', include('customers.urls')),
    path('api/', include('accounts.urls')),
    path('api/', include('cards.urls')),
    path('api/', include('transfers.urls')),
    path('api/', include('transactions.urls')),
    path('api/', include('notifications.urls')),
    path('api/', include('klik.urls')),
]

