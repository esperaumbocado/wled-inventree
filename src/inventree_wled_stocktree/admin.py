"""Django admin configuration for WLED StockTree plugin."""

from django.contrib import admin
from .models import WledInstance


@admin.register(WledInstance)
class WledInstanceAdmin(admin.ModelAdmin):
    """Admin interface for WLED instances."""
    list_display = ('wled_id', 'ip_address', 'max_leds', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('wled_id', 'ip_address')
    ordering = ('wled_id',)
    readonly_fields = ('created_at', 'updated_at')
