import network
import socket
import time
import uasyncio
import sys

from utils import read_until_null_terminator
import wifi_consts
import json

async def connect_to_wifi():
    """Connects to Wi-Fi asynchronously. Returns True on success, False on failure."""
    wlan = None
    try:
        wlan = network.WLAN(network.STA_IF)
        
        wlan.active(False)
        await uasyncio.sleep(0.2)  # Allow time for deactivation
        
        wlan.active(True)
        
        # Scan for available networks
        networks = wlan.scan()
        ap_found = False
        for net in networks:
            ssid = net[0].decode('utf-8')
            rssi = net[3]
            channel = net[2]
            if ssid == wifi_consts.WIFI_SSID:
                ap_found = True
                
        if not ap_found:
            # Continue anyway to see what happens
            pass

        if not wlan.isconnected():
            wlan.connect(wifi_consts.WIFI_SSID, wifi_consts.WIFI_PASSWORD)
            
            max_wait = 20  # Increased wait time
            while max_wait > 0:
                status = wlan.status()
                if status == network.STAT_GOT_IP or status < 0:
                    break
                max_wait -= 1
                await uasyncio.sleep(1)  # Use async sleep
        
        if wlan.isconnected():
            return True
        else:
            status = wlan.status()
            error_message = "Unknown error"
            if status == 1:
                error_message = "CONNECTING"
            elif status == 200:
                error_message = "NO_AP_FOUND"
            elif status == 201:
                error_message = "WRONG_PASSWORD"
            elif status == 202:
                error_message = "NO_AP_FOUND again"
            elif status == 203:
                error_message = "CONNECTION_FAILED"
            elif status == 204:
                error_message = "HANDSHAKE_TIMEOUT"
            elif status == 210:
                error_message = "BEACON_TIMEOUT - AP not responding"
            
            wlan.active(False)  # Try to deactivate on failure
            return False
            
    except OSError as e:
        sys.print_exception(e)
        if wlan:
            try:
                wlan.active(False)  # Try to ensure it's off
            except Exception as e_deact:
                sys.print_exception(e_deact)
        return False
    except Exception as e:
        sys.print_exception(e)
        if wlan:
            try:
                wlan.active(False)
            except Exception as e_deact:
                sys.print_exception(e_deact)
        return False


async def send_message(message: bytes, json_response: bool = True) -> dict | None:
    reader = None
    writer = None
    try:
        reader, writer = await uasyncio.wait_for(
            uasyncio.open_connection(wifi_consts.ACCESS_POINT_IP_ADDRESS, wifi_consts.PORT),
            timeout=10.0
        )
        
        request_message = message + b"\x00"
        writer.write(request_message)
        await writer.drain()
        raw_data = await uasyncio.wait_for(
            read_until_null_terminator(reader),
            timeout=10.0
        )

        writer.write(b"ACK")
        await writer.drain()

        if not raw_data:
            return None
        elif raw_data == b"UNKNOWN_REQUEST":
            print(f"Unknown request: {message}")
            return None
        
        if not json_response:
            return raw_data
        
        try:
                payload_json_str = raw_data.decode('utf-8')
                payload_dict = json.loads(payload_json_str)
                return payload_dict
        except json.JSONDecodeError as e:
            sys.print_exception(e)
            return None
        except UnicodeDecodeError as e:
            sys.print_exception(e)
            return None

    except uasyncio.TimeoutError:
        return None
    except OSError as e:
        if e.errno == 118:
            return None
        else:
            sys.print_exception(e)
            return None
    except Exception as e:
        sys.print_exception(e)
        return None
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


async def fetch_animation_data() -> str | None:
    """Fetches animation data from AP socket asynchronously. Assumes Wi-Fi is connected."""
    data = await send_message(b"GET_ANIMATION")
    if data is not None:
        animation_name = data.get('animation')
        print(f"Received animation: {animation_name}")
        return animation_name
    

async def is_wifi_connected():
    """Asynchronously checks the current Wi-Fi connection status."""
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()

async def main():
    animation = await fetch_animation_data()


if __name__ == "__main__":
    if connect_to_wifi():
        try:
            uasyncio.run(main())
        except Exception as e:
            sys.print_exception(e)
