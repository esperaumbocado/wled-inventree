"""Use WLED to locate InvenTree StockLocations.."""

import json
import logging
import time
import threading

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import re_path, reverse
from django.utils.translation import gettext_lazy as _

import requests
from stock.models import StockLocation
from stock.models import StockItem

from common.notifications import NotificationBody
from InvenTree.helpers_model import notify_users
from plugin import InvenTreePlugin
from plugin.mixins import LocateMixin, SettingsMixin, UrlsMixin

logger = logging.getLogger("inventree")


def superuser_check(user):
    """Check if a user is a superuser."""
    return user.is_superuser


class WledInventreePlugin(UrlsMixin, LocateMixin, SettingsMixin, InvenTreePlugin):
    """Use WLED to locate InvenTree StockLocations.."""

    NAME = "WledInventreePlugin"
    SLUG = "inventree-wled-stocktree"
    TITLE = "WLED StockTree"

    NO_LED_NOTIFICATION = NotificationBody(
        name=_("No location for {verbose_name}"),
        slug="{app_label}.no_led_{model_name}",
        message=_("No LED number is assigned for {verbose_name}"),
    )

    SETTINGS = {
        "ADDRESS": {
            "name": _("IP Address"),
            "description": _("IP address of your WLED device"),
        },
        "MAX_LEDS": {
            "name": _("Max LEDs"),
            "description": _("Maximum number of LEDs in your WLED device"),
            "default": 1,
            "validator": [
                int,
                MinValueValidator(1),
            ],
        },
    }

    superusers = list(get_user_model().objects.filter(is_superuser=True).all())

    def locate_stock_location(self, location_pk):
        """Locate a StockLocation and its parent (if any), with debug prints."""
        print(f"[DEBUG] Attempting to locate location ID {location_pk}")

        try:
            location = StockLocation.objects.get(pk=location_pk)
            print(f"[DEBUG] Found location: {location.name} (ID: {location.pk})")

            led_nbr = location.get_metadata("wled_led")
            print(f"[DEBUG] Location LED metadata: {led_nbr}")

            led_nbr = int(led_nbr) if led_nbr is not None else -1

            parent_led_nbr = None
            if location.parent:
                print(f"[DEBUG] Location has parent: {location.parent.name} (ID: {location.parent.pk})")
                parent_led = location.parent.get_metadata("wled_led")
                print(f"[DEBUG] Parent LED metadata: {parent_led}")

                if parent_led is not None:
                    parent_led_nbr = int(parent_led)

            if led_nbr >= 0:
                print(f"[DEBUG] Lighting up LED {led_nbr} for location {location.name}")
                self._set_led(led_nbr, turn_off_others=True)  # Only turn on this LED, don't turn off others

            if parent_led_nbr is not None and parent_led_nbr != led_nbr:
                print(f"[DEBUG] Lighting up LED {parent_led_nbr} for parent location {location.parent.name}")
                self._set_led(parent_led_nbr, turn_off_others=False)  # Turn off all LEDs before turning on the parent LED

            if led_nbr < 0 and parent_led_nbr is None:
                print(f"[DEBUG] No LED defined for location {location.name} or its parent.")
                notify_users(
                    self.superusers,
                    location,
                    StockLocation,
                    content=self.NO_LED_NOTIFICATION,
                )

        except StockLocation.DoesNotExist:
            print(f"[DEBUG] Location ID {location_pk} does not exist!")
        except ValueError as e:
            print(f"[DEBUG] Invalid LED value: {e}")



    def locate_stock_item(self, item_pk):
        """Localiza um StockItem e ativa a localização.

        Args:
            item_pk (int): Chave primária do StockItem
        """
        logger.info(f"Attempting to locate StockItem ID {item_pk}")

        try:
            item = StockItem.objects.get(pk=item_pk)
            location_pk = item.location_id  # Obtém o local do item

            if location_pk:
                logger.info(f"StockItem {item_pk} está na localização {location_pk}")

                # Tenta localizar o StockLocation correspondente
                self.locate_stock_location(location_pk)

                # Marca o item como localizado
                item.set_metadata("located", True)
            else:
                logger.warning(f"StockItem {item_pk} não tem localização definida!")

        except StockItem.DoesNotExist:
            logger.error(f"StockItem ID {item_pk} não existe!")

    def view_off(self, request):
        """Turn off all LEDs."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")

        self._set_led(request=request)
        return redirect(self.settings_url)

    def view_unregister(self, request, pk):
        """Unregister an LED."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")

        try:
            item = StockLocation.objects.get(pk=pk)
            item.set_metadata("wled_led", None)
        except StockLocation.DoesNotExist:
            pass
        return redirect(self.settings_url)

    def view_register(self, request, pk=None, led=None, context=None):
        """Register an LED."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")

        if pk is None and led is None and str(request.body, encoding="utf8") == "":
            return JsonResponse(
                {
                    "actions": {
                        "POST": [
                            "stocklocation",
                            "led",
                        ],
                    }
                }
            )
        elif request.body is not None:
            data = json.loads(request.body)
            pk = data.get("stocklocation")
            led = data.get("led")

        try:
            item = StockLocation.objects.get(pk=pk)
            previous_entry = item.get_metadata("wled_led")
            item.set_metadata("wled_led", led)
            if previous_entry and previous_entry != led:
                return JsonResponse(
                    {
                        "success": f"Location was registered to {previous_entry}, changed to {led}",
                    }
                )
            return JsonResponse(
                {
                    "success": "Allocation registered, refresh the page to see it in the list"
                }
            )
        except StockLocation.DoesNotExist:
            pass
        return redirect(self.settings_url)

    def setup_urls(self):
        """Return the URLs defined by this plugin."""
        return [
            re_path(r"off/", self.view_off, name="off"),
            re_path(
                r"unregister/(?P<pk>\d+)/", self.view_unregister, name="unregister"
            ),
            re_path(
                r"register/(?P<pk>\d+)/(?P<led>\w+)/",
                self.view_register,
                name="register",
            ),
            re_path(r"register/", self.view_register, name="register-simple"),
        ]

    def get_settings_content(self, request):
        """Add context to the settings panel."""
        stocklocations = StockLocation.objects.filter(metadata__isnull=False).all()

        target_locs = [
            {"name": loc.pathstring, "led": loc.get_metadata("wled_led"), "id": loc.id}
            for loc in stocklocations
            if loc.get_metadata("wled_led")
        ]
        stock_strings = "".join(
            [
                f"""<tr>
            <td>{a["name"]}</td>
            <td>{a["led"]}</td>
            <td><a class="btn btn-primary" href="{reverse("plugin:inventree-wled-stocktree:unregister", kwargs={"pk": a["id"]})}">unregister</a></td>
        </tr>"""
                for a in target_locs
            ]
        )
        return f"""
        <h3>WLED controls</h3>
        <a class="btn btn-primary" href="{reverse('plugin:inventree-wled-stocktree:off')}">Turn off</a>
        <button class="btn btn-primary" onclick="led_register()">Register LED</button>
        <table class="table table-striped">
            <thead><tr><th>Location</th><th>LED</th><th>Actions</th></tr></thead>
            <tbody>{stock_strings}</tbody>
        </table>
        <script>
        function led_register() {{
            constructForm('{reverse("plugin:inventree-wled-stocktree:register-simple")}', {{
                title: 'Register LED',
                actions: 'POST',
                method: 'POST',
                url: '{reverse("plugin:inventree-wled-stocktree:register-simple")}',
                fields: {{
                    'stocklocation': {{'model': 'stocklocation', label: 'Location', type: 'related field', api_url: '{reverse("api-location-list")}', required: true, }},
                    'led': {{'label': 'LED', 'type': 'integer', 'min': 0, 'max': {self.get_setting("MAX_LEDS")} }},
                }},
            }});
        }}

        </script>
        """

    @staticmethod
    def turn_off_led(base_url, target_led):
        """Turn off a specific LED after 10 seconds."""
        time.sleep(10)  # Wait for 10 seconds
        color_black = "000000"
        requests.post(
            base_url,
            json={"seg": {"i": [target_led, color_black]}},
            timeout=3,
        )

    def _set_led(self, target_led: int = None, request=None, turn_off_others=True):
        """Turn on a specific LED, optionally turning off other LEDs, and schedule turning it off."""
        print(f"[DEBUG] turn_off_others: {turn_off_others}")
        address = self.get_setting("ADDRESS")
        max_leds = self.get_setting("MAX_LEDS")

        if not address:
            if request:
                messages.add_message(request, messages.WARNING, "No IP address set for WLED")
            return

        base_url = f"http://{address}/json/state"
        color_black = "000000"
        color_marked = "FF0000"

        # If turn_off_others is True, we turn off all LEDs first
        if turn_off_others:
            print(f"[DEBUG] Turning off all LEDs before turning on LED {target_led}")
            requests.post(
                base_url,
                json={"seg": {"i": [0, max_leds, color_black]}},
                timeout=3,
            )

        # Turn on the specific target LED
        if target_led is not None:
            print(f"[DEBUG] Turning on LED {target_led}")
            requests.post(
                base_url,
                json={"seg": {"i": [target_led, color_marked]}},
                timeout=3,
            )

            # Schedule the LED to turn off after 10 seconds
            threading.Thread(target=self.turn_off_led, args=(base_url, target_led), daemon=True).start()


            