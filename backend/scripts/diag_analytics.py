import django
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.test import RequestFactory
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.hr.views import AnalyticsViewSet

u = User.objects.get(username="admin")
rf = RequestFactory()
req = rf.get("/api/v1/hr/analytics/structure/")
dreq = Request(req)
dreq.user = u
dreq.auth = str(RefreshToken.for_user(u).access_token)

view = AnalyticsViewSet()
view.request = dreq
view.kwargs = {}
view.format_kwarg = None
view.action = "structure"
try:
    r = view.structure(dreq)
    print("OK", r.status_code, r.data)
except Exception:
    traceback.print_exc()
