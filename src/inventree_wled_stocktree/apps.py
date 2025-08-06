"""Django app configuration for WLED StockTree plugin."""

from django.apps import AppConfig


class InventreeWledStocktreeConfig(AppConfig):
    """App configuration for the WLED StockTree plugin."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventree_wled_stocktree'
    verbose_name = 'WLED StockTree'
