"""Django models for WLED StockTree plugin."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class WledInstance(models.Model):
    """Model to store WLED instance information."""
    wled_id = models.PositiveIntegerField(unique=True, verbose_name=_("WLED ID"))
    name = models.CharField(max_length=100, blank=True, verbose_name=_("Custom Name"))
    ip_address = models.GenericIPAddressField(verbose_name=_("IP Address"))
    max_leds = models.PositiveIntegerField(default=1, verbose_name=_("Max LEDs"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        ordering = ['wled_id']
        verbose_name = _("WLED Instance")
        verbose_name_plural = _("WLED Instances")
        app_label = 'inventree_wled_stocktree'
    
    def __str__(self):
        if self.name:
            return f"{self.name} (WLED {self.wled_id})"
        return f"WLED {self.wled_id} ({self.ip_address})"
    
    @property
    def display_name(self):
        """Return the display name for this instance."""
        if self.name:
            return f"{self.name} (WLED {self.wled_id})"
        return f"WLED {self.wled_id}"
