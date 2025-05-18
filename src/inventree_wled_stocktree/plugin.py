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
        """Locate a StockLocation and its parent (if any), supporting two LED ranges with possibly different instances."""
        try:
            parent = StockLocation.objects.get(pk=location_pk)
            if parent.parent:
                parent = parent.parent
            location = StockLocation.objects.get(pk=location_pk)
            x_min = location.get_metadata("wled_x_min")
            x_max = location.get_metadata("wled_x_max")
            y_min = location.get_metadata("wled_y_min")
            y_max = location.get_metadata("wled_y_max")
            instance_id_x = location.get_metadata("wled_instance_id_x")
            instance_id_y = location.get_metadata("wled_instance_id_y")

            x_min = int(x_min) if x_min is not None else None
            x_max = int(x_max) if x_max is not None else None
            y_min = int(y_min) if y_min is not None else None
            y_max = int(y_max) if y_max is not None else None
            instance_id_x = int(instance_id_x) if instance_id_x is not None else None
            instance_id_y = int(instance_id_y) if instance_id_y is not None else None

            wled_list = self.get_wled_instances()
            instance_map = {w["id"]: w["ip"] for w in wled_list if "id" in w and "ip" in w}
            instance_max_leds = {w["id"]: w.get("max_leds", 1) for w in wled_list if "id" in w}

            import threading

            def clear_leds(ip, max_leds):
                try:
                    requests.post(
                        f"http://{ip}/json/state",
                        json={"seg": [{"start": 0, "stop": max_leds, "col": [["000000", "000000", "000000"]]}]},
                        timeout=3,
                    )
                except Exception as e:
                    logger.warning(f"Failed to clear all LEDs on {ip}: {e}")

            threads = []
            for instance_id, ip in instance_map.items():
                max_leds = instance_max_leds.get(instance_id, 1)
                t = threading.Thread(target=clear_leds, args=(ip, max_leds))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            # LED X range (required)
            if x_min is not None and x_max is not None and instance_id_x in instance_map:
                self._set_leds(
                    ip=instance_map[instance_id_x],
                    min_led=x_min,
                    max_led=x_max,
                    color="FF0000"
                )

            # LED Y range (optional, can be on a different instance)
            if y_min is not None and y_max is not None and instance_id_y in instance_map:
                self._set_leds(
                    ip=instance_map[instance_id_y],
                    min_led=y_min,
                    max_led=y_max,
                    color="FF0000"
                )

            # TURN PARENT LED ON
            if parent:
                parent_x_min = int(parent.get_metadata("wled_x_min"))
                parent_x_max = int(parent.get_metadata("wled_x_max"))
                parent_instance_id_x = int(parent.get_metadata("wled_instance_id_x"))

                if parent_x_min is not None and parent_x_max is not None and parent_instance_id_x in instance_map:
                    self._set_leds(
                        ip=instance_map[parent_instance_id_x],
                        min_led=parent_x_min,
                        max_led=parent_x_max,
                        color="FF0000"
                    )

            # ...parent and notification logic unchanged...
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
            item.set_metadata("wled_x_min", None)
            item.set_metadata("wled_x_max", None)
            item.set_metadata("wled_y_min", None)
            item.set_metadata("wled_y_max", None)
            item.set_metadata("wled_instance_id_x", None)
            item.set_metadata("wled_instance_id_y", None)
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
        """Register one or two LED ranges and their WLED instances."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can perform this action")

        if request.method == "POST":
            pk = request.POST.get("stocklocation")
            x_min = request.POST.get("x_min")
            x_max = request.POST.get("x_max")
            y_min = request.POST.get("y_min")
            y_max = request.POST.get("y_max")
            instance_id_x = request.POST.get("wled_instance_id_x")
            instance_id_y = request.POST.get("wled_instance_id_y")

            try:
                item = StockLocation.objects.get(pk=pk)
                item.set_metadata("wled_x_min", x_min)
                item.set_metadata("wled_x_max", x_max)
                item.set_metadata("wled_instance_id_x", instance_id_x)
                if y_min and y_max and instance_id_y:
                    item.set_metadata("wled_y_min", y_min)
                    item.set_metadata("wled_y_max", y_max)
                    item.set_metadata("wled_instance_id_y", instance_id_y)
                else:
                    item.set_metadata("wled_y_min", None)
                    item.set_metadata("wled_y_max", None)
                    item.set_metadata("wled_instance_id_y", None)
                messages.success(request, f"Registered LED range(s) for StockLocation {item.pathstring}")
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
            x_min = loc.get_metadata("wled_x_min")
            x_max = loc.get_metadata("wled_x_max")
            y_min = loc.get_metadata("wled_y_min")
            y_max = loc.get_metadata("wled_y_max")
            instance_id_x = loc.get_metadata("wled_instance_id_x")
            instance_id_y = loc.get_metadata("wled_instance_id_y")
            if x_min and x_max:
                target_locs.append({
                    "name": loc.pathstring,
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_min,
                    "y_max": y_max,
                    "id": loc.id,
                    "instance_x": instance_id_x,
                    "instance_y": instance_id_y,
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


    def _set_leds(self, ip: str, min_led: int, max_led: int, color: str = "FF0000", request=None):
        """Set a color on a range of LEDs (min to max) on a given WLED IP."""
        if not ip:
            if request:
                messages.add_message(request, messages.WARNING, "No IP address provided for WLED")
            return

        if min_led > max_led:
            if request:
                messages.add_message(request, messages.ERROR, "Invalid LED range: min > max")
            return

        base_url = f"http://{ip}/json/state"

        segment = {
            "start": min_led,
            "stop": max_led + 1,  # stop is exclusive
            "col": [color] if isinstance(color, str) else color  # Accept single or list of colors
        }

        payload = {
            "seg": [segment]
        }

        try:
            response = requests.post(base_url, json=payload, timeout=3)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to set LEDs {min_led}-{max_led} on {ip}: {e}")
            if request:
                messages.add_message(request, messages.ERROR, f"Failed to set LEDs on {ip}")

        # Optional: turn off the LEDs after a delay
        def turn_off_range():
            import time
            time.sleep(10)
            off_payload = {
                "seg": [{
                    "start": min_led,
                    "stop": max_led + 1,
                    "col": ["000000"]
                }]
            }
            try:
                requests.post(base_url, json=off_payload, timeout=3)
            except Exception as e:
                logger.warning(f"Failed to turn off LEDs {min_led}-{max_led} on {ip}: {e}")

        threading.Thread(target=turn_off_range, daemon=True).start()