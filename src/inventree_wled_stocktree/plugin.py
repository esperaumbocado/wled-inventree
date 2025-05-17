"""Use WLED to locate InvenTree StockLocations.."""

import json
import logging
import time
import threading
import os

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import re_path, reverse
from django.utils.translation import gettext_lazy as _

import requests
from stock.models import StockLocation, StockItem

from common.notifications import NotificationBody
from InvenTree.helpers_model import notify_users
from plugin import InvenTreePlugin
from plugin.mixins import LocateMixin, SettingsMixin, UrlsMixin

logger = logging.getLogger("inventree")


def superuser_check(user):
    """Check if a user is a superuser."""
    return user.is_superuser


class WledInventreePlugin(UrlsMixin, LocateMixin, SettingsMixin, InvenTreePlugin):
    """Use WLED to locate InvenTree StockLocations."""

    @property
    def dashboard_url(self):
        """Return the URL for the custom dashboard."""
        return reverse("plugin:inventree-wled-stocktree:dashboard")

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

    def locate_stock_location(self, location_pk):
        """Locate a StockLocation and its parent (if any)."""
        try:
            location = StockLocation.objects.get(pk=location_pk)
            led_nbr = location.get_metadata("wled_led")
            instance_id = location.get_metadata("wled_instance_id")

            led_nbr = int(led_nbr) if led_nbr is not None else -1
            instance_id = int(instance_id) if instance_id is not None else None

            parent_led_nbr = None
            parent_instance_id = None
            if location.parent:
                parent_led = location.parent.get_metadata("wled_led")
                parent_instance = location.parent.get_metadata("wled_instance_id")
                if parent_led is not None:
                    parent_led_nbr = int(parent_led)
                if parent_instance is not None:
                    parent_instance_id = int(parent_instance)

            # Load WLED instance list
            wled_list = self.get_wled_instances()
            instance_map = {w["id"]: w["ip"] for w in wled_list if "id" in w and "ip" in w}

            if led_nbr >= 0 and instance_id in instance_map:
                self._set_led(led_nbr, ip=instance_map[instance_id], turn_off_others=True)

            if parent_led_nbr is not None and (not(parent_led_nbr == led_nbr and parent_instance_id == instance_id)):
                if parent_instance_id in instance_map:
                    self._set_led(parent_led_nbr, ip=instance_map[parent_instance_id], turn_off_others=False)

            if led_nbr < 0 and parent_led_nbr is None:
                notify_users(
                    list(get_user_model().objects.filter(is_superuser=True)),
                    location,
                    StockLocation,
                    content=self.NO_LED_NOTIFICATION,
                )

        except StockLocation.DoesNotExist:
            logger.debug(f"Location ID {location_pk} does not exist!")
        except ValueError as e:
            logger.debug(f"Invalid metadata value: {e}")


    def locate_stock_item(self, item_pk):
        """Locate a StockItem and activate its location."""
        try:
            item = StockItem.objects.get(pk=item_pk)
            location_pk = item.location_id
            if location_pk:
                self.locate_stock_location(location_pk)
                item.set_metadata("located", True)
            else:
                logger.warning(f"StockItem {item_pk} has no defined location!")
        except StockItem.DoesNotExist:
            logger.error(f"StockItem ID {item_pk} does not exist!")

    def view_off(self, request):
        """Turn off all LEDs."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")
        self._set_led(request=request)
        return redirect(self.settings_url)

    def view_unregister(self, request, pk):
        """Unregister an LED."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can perform this action")

        try:
            item = StockLocation.objects.get(pk=pk)
            item.set_metadata("wled_led", None)
        except StockLocation.DoesNotExist:
            pass
        return redirect(self.dashboard_url)
    
    def view_register_wled(self, request, pk=None, led=None):
        # Only superusers allowed
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can perform this action")

        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)

        wled_ip = request.POST.get('wled_ip')
        wled_max_leds = request.POST.get('wled_max_leds', 1)

        if not wled_ip:
            return JsonResponse({'error': 'Missing WLED IP'}, status=400)

        json_file_path = './wled_instances.json'

        # Load existing data
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as f:
                try:
                    wled_list = json.load(f)
                except json.JSONDecodeError:
                    wled_list = []
        else:
            wled_list = []

        # Prevent duplicate IP registration
        for wled in wled_list:
            if wled.get('ip') == wled_ip:
                return JsonResponse({'error': 'WLED with this IP already registered'}, status=400)

        # Determine new ID
        if wled_list:
            last_id = max(w.get('id', 0) for w in wled_list)
        else:
            last_id = 0

        new_id = last_id + 1

        # Add new instance
        wled_list.append({
            'id': new_id,
            'ip': wled_ip,
            'max_leds': int(wled_max_leds)
        })

        # Save updated list
        with open(json_file_path, 'w') as f:
            json.dump(wled_list, f, indent=2)

        return JsonResponse({'success': True, 'wled_list': wled_list})
    
    def view_unregister_wled(self, request):
        # Only superusers allowed
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can perform this action")
        
        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)

        # Expecting ID for unregistration
        wled_id = request.POST.get('wled_id')
        
        if not wled_id:
            return JsonResponse({'error': 'Missing WLED ID to unregister'}, status=400)
        
        try:
            wled_id = int(wled_id)
        except ValueError:
            return JsonResponse({'error': 'WLED ID must be an integer'}, status=400)

        json_file_path = './wled_instances.json'

        if not os.path.exists(json_file_path):
            return JsonResponse({'error': 'No WLED instances found'}, status=404)

        with open(json_file_path, 'r') as f:
            try:
                wled_list = json.load(f)
            except json.JSONDecodeError:
                wled_list = []

        original_len = len(wled_list)

        # Filter out the instance with the matching ID
        wled_list = [w for w in wled_list if w.get('id') != wled_id]

        if len(wled_list) == original_len:
            return JsonResponse({'error': 'No matching WLED instance found with given ID'}, status=404)

        with open(json_file_path, 'w') as f:
            json.dump(wled_list, f, indent=2)

        return JsonResponse({'success': True, 'wled_list': wled_list})

        

    def view_register(self, request, pk=None, led=None, context=None):
        """Register an LED and its WLED instance."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can perform this action")

        if request.method == "POST":
            pk = request.POST.get("stocklocation")
            led = request.POST.get("led")
            instance_id = request.POST.get("wled_instance_id")

            try:
                item = StockLocation.objects.get(pk=pk)

                previous_led = item.get_metadata("wled_led")
                previous_instance = item.get_metadata("wled_instance_id")

                item.set_metadata("wled_led", led)
                item.set_metadata("wled_instance_id", instance_id)

                msg = "Registered LED {led} for StockLocation {name}".format(
                    led=led, name=item.pathstring
                )
                if previous_led != led or previous_instance != instance_id:
                    messages.success(request, msg)
                else:
                    messages.info(request, "No changes made.")

            except StockLocation.DoesNotExist:
                messages.error(request, "StockLocation does not exist.")
                return redirect(self.dashboard_url)

        return redirect(self.dashboard_url)

    def view_dashboard(self, request):
        """Custom dashboard view for LED registration."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can view the LED dashboard")

        stocklocations = StockLocation.objects.filter(metadata__isnull=False)
        wled_instances = self.get_wled_instances()

        target_locs = []
        for loc in stocklocations:
            led = loc.get_metadata("wled_led")
            instance_id = loc.get_metadata("wled_instance_id")
            if led:
                target_locs.append({
                    "name": loc.pathstring,
                    "led": led,
                    "id": loc.id,
                    "instance": instance_id,  # Only the ID
                })

        max_leds = self.get_setting("MAX_LEDS")

        return render(request, 'inventree_wled_stocktree/dashboard.html', {
            'target_locs': target_locs,
            'max_leds': max_leds,
            'wled_instances': wled_instances,
        })


    
    def get_wled_instances(self):
        json_file_path = './wled_instances.json'  # Adjust this path
        
        if not os.path.exists(json_file_path):
            return []
        
        try:
            with open(json_file_path, 'r') as f:
                wled_list = json.load(f)
                return wled_list
        except (json.JSONDecodeError, IOError):
            return []

    def setup_urls(self):
        """Return the URLs defined by this plugin."""
        return [
            re_path(r"settings", self.view_dashboard, name="dashboard"),
            re_path(r"off/", self.view_off, name="off"),
            re_path(r"unregister/(?P<pk>\d+)/", self.view_unregister, name="unregister"),
            re_path(r"register/", self.view_register, name="register-simple"),
            re_path(r"register-wled/", self.view_register_wled, name="register-wled"),
            re_path(r"unregister-wled/", self.view_unregister_wled, name="unregister-wled"),
        ]

    @staticmethod
    def turn_off_led(base_url, target_led):
        """Turn off a specific LED after 10 seconds."""
        time.sleep(10)
        requests.post(
            base_url,
            json={"seg": {"i": [target_led, "000000"]}},
            timeout=3,
        )

    def _set_led(self, target_led: int = None, ip: str = None, request=None, turn_off_others=True):
        """Turn on a specific LED on a given WLED IP."""
        if not ip:
            if request:
                messages.add_message(request, messages.WARNING, "No IP address provided for WLED")
            return

        max_leds = self.get_setting("MAX_LEDS")

        base_url = f"http://{ip}/json/state"
        color_black = "000000"
        color_marked = "FF0000"

        if turn_off_others:
            try:
                requests.post(
                    base_url,
                    json={"seg": {"i": [0, max_leds, color_black]}},
                    timeout=3,
                )
            except Exception as e:
                logger.warning(f"Failed to reset all LEDs on {ip}: {e}")

        if target_led is not None:
            try:
                requests.post(
                    base_url,
                    json={"seg": {"i": [target_led, color_marked]}},
                    timeout=3,
                )
                threading.Thread(target=self.turn_off_led, args=(base_url, target_led), daemon=True).start()
            except Exception as e:
                logger.warning(f"Failed to set LED {target_led} on {ip}: {e}")
