from django.urls import path
from .views import (
    report_dashboard,
    export_revenue_report,
    export_cost_report,
    export_review_report,
)

urlpatterns = [
    path('', report_dashboard, name='report_dashboard'),
    path('export/revenue/', export_revenue_report, name='export_revenue_report'),
    path('export/cost/',    export_cost_report,    name='export_cost_report'),
    path('export/review/',  export_review_report,  name='export_review_report'),
]