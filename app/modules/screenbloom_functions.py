from beautifulhue.api import Bridge
# from colorthief import ColorThief
from time import sleep, time
from PIL import ImageGrab
from config import params
import ConfigParser
import webbrowser
import threading
import traceback
import StringIO
import requests
import urllib2
import rgb_cie
import random
import json
import ast
import sys
import os

# import webcolors

if params.BUILD == 'win':
    config_path = os.getenv('APPDATA')
elif params.BUILD == 'mac':
    config_path = ''
    if getattr(sys, 'frozen', False):
        config_path = os.path.dirname(sys.executable)
    elif __file__:
        config_path = os.path.dirname(__file__)


# Class for the start-up process
class StartupThread(threading.Thread):
    def __init__(self, host):
        super(StartupThread, self).__init__()
        self.stoprequest = threading.Event()
        self.host = host

    def run(self):
        if not self.stoprequest.isSet():
            # Check if config file has been created yet
            config_exists = os.path.isfile(config_path + '\\screenbloom_config.cfg')
            if config_exists:
                print 'Config already exists'
                config = ConfigParser.RawConfigParser()
                config.read(config_path + '\\screenbloom_config.cfg')
                write_config('App State', 'running', '0')

                # Wait for 200 status code from server then load up interface
                while not check_server(self.host):
                    sleep(0.2)

                # Grab attributes from config file
                atr = initialize()

                # Initialize screen object
                global _screen
                _screen = Screen(*atr)

                url = 'http://%s:5000/' % self.host
                webbrowser.open(url)
            else:
                # Config file doesn't exist, open New User interface
                print 'Config does not exist yet!'
                url = 'http://%s:5000/new-user' % self.host
                webbrowser.open(url)

    def join(self, timeout=None):
        self.stoprequest.set()
        super(StartupThread, self).join(timeout)


# Class for running ScreenBloom thread
class ScreenBloomThread(threading.Thread):
    def __init__(self, update):
        super(ScreenBloomThread, self).__init__()
        self.stoprequest = threading.Event()
        self.update = float(update)

    def run(self):
        while not self.stoprequest.isSet():
            start = time()
            run()
            end = time()
            elapsed_time = end - start
            print 'Elapsed Time: %.2f' % elapsed_time

    def join(self, timeout=None):
        self.stoprequest.set()
        super(ScreenBloomThread, self).join(timeout)


# Class for Screen object to hold values during runtime
class Screen(object):
    def __init__(self, bridge, ip, devicename, bulbs, default, rgb, update, max_bri, min_bri, zones, zone_state, mode, black_rgb, color_buffer):
        self.bridge = bridge
        self.ip = ip
        self.devicename = devicename
        self.bulbs = bulbs
        self.default = default
        self.rgb = rgb
        self.update = update
        self.max_bri = max_bri
        self.min_bri = min_bri
        self.zones = zones
        self.zone_state = zone_state
        self.mode = mode
        self.black_rgb = black_rgb
        self.color_buffer = color_buffer

converter = rgb_cie.Converter()  # Class for easy conversion of RGB to Hue CIE


# Write traceback to logfile
def write_traceback():
    with open('log.txt', 'a+') as f:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, file=f)


# Generate truly random RGB
def party_rgb():
    r = lambda: random.randint(0, 255)
    rgb = (r(), r(), r())
    return rgb


# Check server status
def check_server(host):
    try:
        r = requests.get('http://%s:5000/new-user' % host)
        response = r.status_code
    except requests.ConnectionError:
        response = 404
    if response == 200:
        return True
    else:
        return False


# Return list of current Hue light IDs
def get_lights_list(hue_ip, username):
    bridge = Bridge(device={'ip': hue_ip}, user={'name': username})
    resource = {
        'which': 'all'
    }
    lights = bridge.light.get(resource)
    lights = lights['resource']

    lights_list = []
    for light in lights:
        try:
            lights_list.append(str(light['id']))
        except Exception as e:
            print '\nWhooooops!'
            print light
            print e
    return lights_list


# Return more detailed information about specified lights
def get_lights_data(hue_ip, username):
    bridge = Bridge(device={'ip': hue_ip}, user={'name': username})
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')
    all_lights = config.get('Light Settings', 'all_lights')
    all_lights = [int(i) for i in all_lights.split(',')]
    active_bulbs = config.get('Light Settings', 'active')
    active_bulbs = [int(i) for i in active_bulbs.split(',')]

    lights = []

    for counter, light in enumerate(all_lights):
        resource = {
            'which': light
        }
        result = bridge.light.get(resource)

        # Skip unavailable lights
        if type(result['resource']) is dict:
            state = result['resource']['state']['on']
            light_name = result['resource']['name']
            light_data = [light, state, light_name, int(active_bulbs[counter])]
            lights.append(light_data)

    return lights


# Create config file on first run
def create_config(hue_ip, username):
    config = ConfigParser.RawConfigParser()
    lights = get_lights_list(hue_ip, username)
    active = ','.join([str(0) for light in lights])

    config.add_section('Configuration')
    config.set('Configuration', 'hue_ip', hue_ip)
    config.set('Configuration', 'username', username)

    config.add_section('Light Settings')
    config.set('Light Settings', 'all_lights', ','.join(lights))
    config.set('Light Settings', 'active', active)
    config.set('Light Settings', 'update', '1.2')
    config.set('Light Settings', 'default', '255,250,240')
    config.set('Light Settings', 'max_bri', '254')
    config.set('Light Settings', 'min_bri', '125')
    config.set('Light Settings', 'zones', '[]')
    config.set('Light Settings', 'zone_state', 0)
    config.set('Light Settings', 'black_rgb', '1,1,1')

    config.add_section('Party Mode')
    config.set('Party Mode', 'running', '0')

    config.add_section('App State')
    config.set('App State', 'running', '0')

    with open(config_path + '\\screenbloom_config.cfg', 'wb') as config_file:
        config.write(config_file)

    # Grab attributes from config file
    atr = initialize()

    # Initialize screen object
    global _screen
    _screen = Screen(*atr)


# Rewrite config file with given arguments
def write_config(section, item, value):
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')
    config.set(section, item, value)

    with open(config_path + '\\screenbloom_config.cfg', 'wb') as config_file:
        config.write(config_file)


# Grab attributes for screen instance
def initialize():
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')

    ip = config.get('Configuration', 'hue_ip')
    username = config.get('Configuration', 'username')
    bridge = Bridge(device={'ip': ip}, user={'name': username})

    max_bri = config.get('Light Settings', 'max_bri')
    min_bri = config.get('Light Settings', 'min_bri')

    active_lights = config.get('Light Settings', 'active')
    active_lights = [int(i) for i in active_lights.split(',')]
    all_lights = config.get('Light Settings', 'all_lights')
    all_lights = [int(i) for i in all_lights.split(',')]

    # Check selected bulbs vs all known bulbs
    bulb_list = []
    for counter, bulb in enumerate(all_lights):
        try:
            if active_lights[counter]:
                bulb_list.append(bulb)
            else:
                bulb_list.append(0)
        except IndexError:
            bulb_list.append(0)

    update = config.get('Light Settings', 'update')
    default = config.get('Light Settings', 'default').split(',')
    default = (int(default[0]), int(default[1]), int(default[2]))

    zones = config.get('Light Settings', 'zones')
    zones = ast.literal_eval(zones)

    zone_state = config.getboolean('Light Settings', 'zone_state')

    # mode = 'dominant'
    mode = 'standard'

    black_rgb = config.get('Light Settings', 'black_rgb').split(',')
    black_rgb = (int(black_rgb[0]), int(black_rgb[1]), int(black_rgb[2]))

    color_buffer = []

    return bridge, ip, username, bulb_list, default, default, \
           update, max_bri, min_bri, zones, zone_state, mode,\
           black_rgb, color_buffer


# Get updated attributes, re-initialize screen object
def re_initialize():
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')

    # Attributes
    at = initialize()

    global _screen
    _screen = Screen(*at)

    # Update bulbs with new settings
    results = screen_avg()

    try:
        # Update Hue bulbs to avg color of screen
        update_bulbs(results['rgb'], results['dark_ratio'])
    except urllib2.URLError:
        print 'Connection timed out, continuing...'
        pass


# Return modified Hue brightness value from ratio of dark pixels
def get_brightness(screen_obj, dark_pixel_ratio):
    max_brightness = int(screen_obj.max_bri)
    min_brightness = int(screen_obj.min_bri)

    normal_range = max(1, max_brightness - 1)
    new_range = max_brightness - min_brightness

    brightness = max_brightness - (dark_pixel_ratio * max_brightness) / 100
    scaled_brightness = (((brightness - 1) * new_range) / normal_range) + float(screen_obj.min_bri) + 1

    return int(scaled_brightness)


# Updates Hue bulbs to specified RGB value
def update_bulbs(new_rgb, dark_ratio):
    brightness = get_brightness(_screen, dark_ratio)
    send_light_commands(new_rgb, brightness)
    _screen.rgb = new_rgb


# Set bulbs to saved default color
def update_bulb_default():
    default_rgb = _screen.default[0], _screen.default[1], _screen.default[2]
    send_light_commands(default_rgb, _screen.max_bri)


# Set bulbs to random RGB
def update_bulb_party():
    print '\nParty Mode! | Brightness: %d' % int(_screen.max_bri)
    party_color = party_rgb()
    send_light_commands(party_color, _screen.max_bri, party=True)


# Convert update speed to ms, check lower bound
def get_transition_time(update_speed):
    update_speed = int(float(update_speed) * 10)
    return update_speed if update_speed > 2 else 2


# Sends Hue API command to bulb
def send_rgb_to_bulb(bulb, rgb, brightness):
    if bulb:  # Only contact active lights
        print 'Sending to Bulb: %s -> Color: %s | Bri: %s' % (str(bulb), str(rgb), str(brightness))

        if int(brightness) < 5:  # Maybe set user controlled darkness threshold here?
            rgb = _screen.black_rgb

        hue_color = converter.rgbToCIE1931(rgb[0], rgb[1], rgb[2])
        resource = {
            'which': bulb,
            'data': {
                'state': {
                    'xy': hue_color,
                    'bri': int(brightness),
                    'transitiontime': get_transition_time(_screen.update)
                }
            }
        }
        _screen.bridge.light.update(resource)


# Used by standard mode
def send_light_commands(rgb, bri, party=False):
    for bulb in _screen.bulbs:
        if party:
            rgb = party_rgb()
            try:
                bri = random.randrange(int(_screen.min_bri), int(bri) + 1)
            except ValueError as e:
                print e
                continue
        send_rgb_to_bulb(bulb, rgb, bri)


# Send on/off Hue API command to bulbs
def lights_on_off(state):
    print '\nTurning Selected Lights %s' % state

    active_lights = _screen.bulbs
    state = True if state == 'On' else False

    for light in active_lights:
        resource = {
            'which': light,
            'data': {
                'state': {
                    'on': state,
                    'bri': int(_screen.max_bri),
                    'transitiontime': _screen.update
                }
            }
        }
        _screen.bridge.light.update(resource)


# Found on StackOverflow: http://stackoverflow.com/a/9694246
# Convert RGB tuple to closest web color name
def closest_colour(requested_colour):
    min_colours = {}
    for key, name in webcolors.css3_hex_to_names.items():
        r_c, g_c, b_c = webcolors.hex_to_rgb(key)
        rd = (r_c - requested_colour[0]) ** 2
        gd = (g_c - requested_colour[1]) ** 2
        bd = (b_c - requested_colour[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]


def get_colour_name(requested_colour):
    try:
        closest_name = actual_name = webcolors.rgb_to_name(requested_colour)
    except ValueError:
        closest_name = closest_colour(requested_colour)
        actual_name = None
    return actual_name, closest_name


def classify_color(color):
    classification = ''
    actual_name, closest_name = get_colour_name(color)
    # print color
    print closest_name
    dim_colors = []
    white_colors = ['aliceblue', 'azure', ]
    vibrant_colors = ['blueviolet', 'brown', 'chartreuse', 'crimson']
    light_colors = ['cyan', ]
    if color == (0, 0, 0):
        classification = 'black'

    return classification


# Return avg color of all pixels and ratio of dark pixels for a given image
def img_avg(img):
    # _screen.mode = 'dominant'
    dominant_color = False
    if _screen.mode == 'dominant':
        # data = StringIO.StringIO()
        # new_image = img.copy()
        # new_image.save(data, format='PNG')
        # color_thief = ColorThief(data)
        # try:
        #     dominant_color = color_thief.get_color(quality=1)
        #     # print dominant_color
        # except Exception as e:
        #     print e
        # img.show()
        colors = img.getcolors()
        sorted_colors = sorted(colors, key=lambda tup: tup[0], reverse=True)
        for entry in sorted_colors[:3]:
            color = entry[1]
            actual_name, closest_name = get_colour_name(color)
            # print color
            # print 'Closest Name: %s' % closest_name
        print '\n%d Total Colors' % len(sorted_colors)
        dominant_color = sorted_colors[0][1]
        classify_color(dominant_color)

    low_threshold = 10
    mid_threshold = 40
    high_threshold = 225
    dark_pixels = 1
    mid_range_pixels = 1
    total_pixels = 1
    r = 1
    g = 1
    b = 1

    # Win version of imgGrab does not contain alpha channel
    if img.mode == 'RGB':
        img.putalpha(0)

    # Create list of pixels
    pixels = list(img.getdata())

    for red, green, blue, alpha in pixels:
        # Don't count pixels that are too dark
        if red < low_threshold and green < low_threshold and blue < low_threshold:
            dark_pixels += 1
        # Or too light
        elif red > high_threshold and green > high_threshold and blue > high_threshold:
            pass
        else:
            if red < mid_threshold and green < mid_threshold and blue < mid_threshold:
                mid_range_pixels += 1
                dark_pixels += 1
            r += red
            g += green
            b += blue
        total_pixels += 1

    n = len(pixels)
    r_avg = r / n
    g_avg = g / n
    b_avg = b / n
    rgb = [r_avg, g_avg, b_avg]

    # If computed average below darkness threshold, set to the threshold
    for index, item in enumerate(rgb):
        if item <= low_threshold:
            rgb[index] = low_threshold

    rgb = (rgb[0], rgb[1], rgb[2])
    if dominant_color:
        rgb = dominant_color

    data = {
        'rgb': rgb,
        'dark_ratio': float(dark_pixels) / float(total_pixels) * 100
    }
    return data


# Grabs screenshot of current window, calls img_avg (including on zones if present)
def screen_avg():
    # Grab image of current screen
    img = ImageGrab.grab()

    # Resize for performance
    size = (16, 9)
    img = img.resize(size)

    zone_result = []
    if _screen.zone_state:
        for zone in _screen.zones:
            box = (int(zone['x1']), int(zone['y1']), int(zone['x2']), int(zone['y2']))
            part_img = img.copy().crop(box)
            part_data = img_avg(part_img)
            part_data['bulbs'] = zone['bulbs']
            zone_result.append(part_data)

    screen_data = img_avg(img)
    screen_data['zones'] = zone_result
    return screen_data


def get_color_buffer_avg(color_buffer):
    rgbs = [entry[0] for entry in color_buffer]
    dark_ratios = [entry[1] for entry in color_buffer]

    r_avg = sum([rgb[0] for rgb in rgbs]) / len(rgbs)
    g_avg = sum([rgb[1] for rgb in rgbs]) / len(rgbs)
    b_avg = sum([rgb[2] for rgb in rgbs]) / len(rgbs)
    rgb_avg = r_avg, g_avg, b_avg
    dark_avg = sum([dark_ratio for dark_ratio in dark_ratios]) / len(dark_ratios)
    return rgb_avg, dark_avg


# Main loop, called on the update speed interval
def run():
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')
    party_mode = config.getboolean('Party Mode', 'running')
    zone_mode = config.getboolean('Light Settings', 'zone_state')
    if party_mode:
        update_bulb_party()
        sleep(float(_screen.update))
    else:
        results = screen_avg()
        # Push to color_buffer
        # _screen.color_buffer.insert(0, [results['rgb'], results['dark_ratio']])
        # if len(_screen.color_buffer) > 2:
        #     # Pop last result, get averages of color_buffer
        #     _screen.color_buffer.pop()
        #     rgb, dark_ratio = get_color_buffer_avg(_screen.color_buffer)
        # else:
        rgb = results['rgb']
        dark_ratio = results['dark_ratio']
        try:
            print '\n'
            if zone_mode:
                print 'Zone Mode | %s color' % _screen.mode
                for zone in results['zones']:
                    brightness = get_brightness(_screen, zone['dark_ratio'])
                    for bulb in zone['bulbs']:
                        send_rgb_to_bulb(bulb, zone['rgb'], brightness)
            else:
                print 'Standard Mode | %s color' % _screen.mode
                update_bulbs(rgb, dark_ratio)
        except urllib2.URLError:
            print 'Connection timed out, continuing...'
            pass


# View Logic ####################################################################################
def get_index_data():
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')

    state = config.get('App State', 'running')
    hue_ip = config.get('Configuration', 'hue_ip')
    username = config.get('Configuration', 'username')
    update = config.get('Light Settings', 'update')
    max_bri = config.get('Light Settings', 'max_bri')
    min_bri = config.get('Light Settings', 'min_bri')
    default = config.get('Light Settings', 'default')
    black = config.get('Light Settings', 'black_rgb')
    zones = config.get('Light Settings', 'zones')
    zone_state = config.getboolean('Light Settings', 'zone_state')
    party_mode = config.getboolean('Party Mode', 'running')

    default_color = default.split(',')
    black_rgb = black.split(',')
    lights = get_lights_data(hue_ip, username)
    zones = ast.literal_eval(zones)

    icon_size = 10
    if len(lights) > 3:
        icon_size = 4

    data = {
        'state': state,
        'update': update,
        'max_bri': max_bri,
        'min_bri': min_bri,
        'default': default,
        'default_color': default_color,
        'black_rgb': black_rgb,
        'lights': lights,
        'lights_number': len(lights),
        'icon_size': icon_size,
        'username': username,
        'party_mode': party_mode,
        'zones': zones,
        'zone_state': zone_state
    }
    return data


def start_screenbloom():
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')
    state = int(config.get('App State', 'running'))
    update = config.get('Light Settings', 'update')
    _screen.bulb_state = 'on'

    if update:
        state = False

    if state:
        data = {
            'message': 'ScreenBloom already running'
        }
    else:
        write_config('App State', 'running', '1')

        global t
        t = ScreenBloomThread(update)
        t.start()

        print '\nHello!'

        data = {
            'message': 'ScreenBloom thread initialized'
        }
    return data


def stop_screenbloom():
    print '\nEnding screenBloom thread...'
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')
    write_config('App State', 'running', '0')

    # End currently running threads
    try:
        t.join()
    except NameError:
        print 'ScreenBloom thread not running'

    update_bulb_default()
    data = {
        'message': 'Successfully ended screenBloom thread'
    }
    return data


def restart_check():
    global t
    config = ConfigParser.RawConfigParser()
    config.read(config_path + '\\screenbloom_config.cfg')
    update = config.get('Light Settings', 'update')

    try:
        if t.isAlive():
            print 'Restarting thread...'
            t.join()
            re_initialize()
            write_config('App State', 'running', '1')

            t = ScreenBloomThread(update)
            t.start()

            print '\nHello!'
        else:
            re_initialize()
    except NameError:
        print 'Thread does not exist yet'
        re_initialize()


def get_screenshot():
    img = ImageGrab.grab()
    data = StringIO.StringIO()
    img.save(data, format="PNG")
    b64_data = data.getvalue().encode('base64')
    return b64_data


# Registration ######################################################
# Parses arguments from AJAX call and passes them to register_device()
# This is a disgusting function
def register_logic(ip, host):
    if not ip:
        print 'Hue IP not entered manually'
        # Attempting to grab IP from Philips uPNP app
        try:
            print 'Attempting to grab bridge IP...'
            requests.packages.urllib3.disable_warnings()
            url = 'https://www.meethue.com/api/nupnp'
            r = requests.get(url, verify=False).json()
            ip = str(r[0]['internalipaddress'])
            print 'Success!  Hue IP: %s' % ip
        except Exception as e:
            write_traceback()
            error_type = 'manual'
            error_description = 'Error grabbing Hue IP, redirecting to manual entry...'
            data = {
                'success': False,
                'error_type': error_type,
                'error_description': error_description,
                'host': host
            }
            return data
    try:
        print 'Attempting to register app with Hue bridge...'
        # Send post request to Hue bridge to register new username, return response as JSON
        result = register_device(ip)
        temp_result = result[0]
        result_type = ''
        for k, v in temp_result.items():
            result_type = str(k)
        if result_type == 'error':
            error_type = result[0]['error']['type']
            error_description = result[0]['error']['description']
            data = {
                'success': False,
                'error_type': str(error_type),
                'error_description': str(error_description)
            }
            return data
        else:
            username = temp_result[result_type]['username']
            create_config(ip, username)
            data = {
                'success': True,
                'message': 'Success!'
            }
            return data
    except requests.exceptions.ConnectionError:
        data = {
            'success': False,
            'error_type': 'Invalid URL',
            'error_description': 'Something went wrong with the connection, please try again...'
        }
        return data
    except IOError:
        data = {
            'success': False,
            'error_type': 'permission',
            'error_description': 'Permission denied, administrator rights needed..'
        }
        return data


# Add username to bridge whitelist
def register_device(hue_ip):
    url = 'http://%s/api/' % hue_ip
    data = {
        'devicetype': 'ScreenBloom'
    }
    body = json.dumps(data)
    r = requests.post(url, data=body, timeout=5)
    return r.json()
