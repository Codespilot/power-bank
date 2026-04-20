from django.contrib import admin

from .models import Item, User, UserRole, Merchant

admin.site.register(Item)
admin.site.register(User)
admin.site.register(UserRole)
admin.site.register(Merchant)
