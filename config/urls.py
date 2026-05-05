from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('', include('meals.urls')),
    path('', include('finance.urls')),
    path('', include('reviews.urls')),
    path('reports/', include('reports.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html'
    ), name='login'),

    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registrations/', include('registrations.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)