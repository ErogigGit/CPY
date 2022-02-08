import time
import busio
import board
import neopixel
import displayio
import microcontroller
import adafruit_adt7410
import adafruit_touchscreen

from analogio import AnalogIn
from adafruit_button import Button
from adafruit_pyportal import PyPortal
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label

from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT

# ------------- Inputs and Outputs Setup ------------- #
try:  # attempt to init. the temperature sensor
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
    adt.high_resolution = True
except ValueError:
    # Did not find ADT7410. Probably running on Titano or Pynt
    adt = None

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# ------------ light sensor setup ------------ #
light_sensor = AnalogIn(board.LIGHT)

# -------------- Sound Effects --------------- #
soundBeep = "/sounds/beep.wav"

# --------------- Screen Setup --------------- #
pyportal = PyPortal()
display = board.DISPLAY
display.rotation = 270

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
"""Use below for Most Boards"""
status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
)

wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

def connected(client):
    # Connected function will be called when the client is connected to Adafruit IO.
    # This is a good place to subscribe to feed changes.  The client parameter
    # passed to this function is the Adafruit IO MQTT client so you can make
    # calls against it easily.
    print("Connected to Adafruit IO!  Listening for DemoFeed changes...")


def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a feed.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))


# pylint: disable=unused-argument
def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    print("Disconnected from Adafruit IO!")


# pylint: disable=unused-argument
def on_message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    # The feed_id parameter identifies the feed, and the payload parameter has
    # the new value.
    print("Feed {0} received new value: {1}".format(feed_id, payload))

def on_battery_msg(client, topic, message):
    # Method called whenever user/feeds/battery has a new value
    print("Battery level: {}v".format(message))

# Connect to WiFi
print("Connecting to WiFi...")
wifi.connect()
print("Connected!")

# Initialize MQTT interface with the esp interface
MQTT.set_socket(socket, esp)

# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    username=secrets["aio_username"],
    password=secrets["aio_key"],
)

# Initialize an Adafruit IO MQTT Client
io = IO_MQTT(mqtt_client)

# Connect the callback methods defined above to Adafruit IO
io.on_connect = connected
io.on_disconnect = disconnected
io.on_subscribe = subscribe
io.on_unsubscribe = unsubscribe
io.on_message = on_message

# Connect to Adafruit IO
print("Connecting to Adafruit IO...")
io.connect()

# Set up a message handler for the battery feed
io.add_feed_callback("digital", on_battery_msg)

# Subscribe to all messages on the battery feed
io.subscribe("digital")

#___________________________#

# Backlight function on screen
def set_backlight(val):
    val = max(0, min(1.0, val))
    board.DISPLAY.auto_brightness = False
    board.DISPLAY.brightness = val

# Set the Backlight
set_backlight(1)

# Touchscreen setup
# ------Rotate 270:
screen_width = 240
screen_height = 320
ts = adafruit_touchscreen.Touchscreen(
    board.TOUCH_YD,
    board.TOUCH_YU,
    board.TOUCH_XR,
    board.TOUCH_XL,
    calibration=((5200, 59000), (5800, 57000)),
    size=(screen_width, screen_height),
)

# ------------- Display Groups ------------- #
splash = displayio.Group(max_size=15)  # The Main Display Group
view1 = displayio.Group(max_size=15)  # Group for View 1 objects
view2 = displayio.Group(max_size=15)  # Group for View 2 objects
view3 = displayio.Group(max_size=15)  # Group for View 3 objects

def hideLayer(hide_target):
    try:
        splash.remove(hide_target)
    except ValueError:
        pass
def showLayer(show_target):
    try:
        time.sleep(0.1)
        splash.append(show_target)
    except ValueError:
        pass

# ------------- Setup for Images ------------- #
pyportal.set_background('/images/loading.bmp')

# ---------- Text Boxes ------------- #
# Set the font and preload letters
font = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf")
font.load_glyphs(b"abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()")

# Default Label styling:
TABS_X = 5
TABS_Y = 40

# text window view 1
feed1_label = Label(font, text="Text Wondow 1", color=0xFFFFFF, max_glyphs=200)
feed1_label.x = TABS_X
feed1_label.y = TABS_Y
view1.append(feed1_label)
#data window view 1
adafruit_data = Label(font, text="Data View", color=0xFFFFFF, max_glyphs=200)
adafruit_data.x = TABS_X
adafruit_data.y = 120
view1.append(adafruit_data)
# text window view 2
feed2_label = Label(font, text="Text Wondow 2", color=0xFFFFFF, max_glyphs=200)
feed2_label.x = TABS_X
feed2_label.y = TABS_Y
view2.append(feed2_label)
# text window view 3
feed3_label = Label(font, text="Data View", color=0xFFFFFF, max_glyphs=200)
feed3_label.x = TABS_X
feed3_label.y = TABS_Y
view3.append(feed3_label)
# data window view 3
sensor_data = Label(font, text="Data View", color=0xFFFFFF, max_glyphs=200)
sensor_data.x = TABS_X
sensor_data.y = 120
view3.append(sensor_data)

# 0x03AD31
text_hight = Label(font, text="M", color=0xFF0000, max_glyphs=10)
# return a reformatted string with word wrapping using PyPortal.wrap_nicely
def text_box(target, top, string, max_chars):
    text = pyportal.wrap_nicely(string, max_chars)
    new_text = ""
    test = ""
    for w in text:
        new_text += "\n" + w
        test += "M\n"
    text_hight.text = test  # Odd things happen without this
    glyph_box = text_hight.bounding_box
    target.text = ""  # Odd things happen without this
    target.y = int(glyph_box[3] / 2) + top
    target.text = new_text

# ---------- Display Buttons ------------- #

# We want three buttons across the top of the screen
TAPS_HEIGHT = 50
TAPS_WIDTH = int(screen_width / 3)
TAPS_Y = 0
buttons = []

# View 1
button_view1 = Button(
    x=0,
    y=0,
    width=TAPS_WIDTH,
    height=TAPS_HEIGHT,
    label="View 1",
    label_font=font,
    label_color=0xFFFFFF,
    fill_color=0x979697,
    outline_color=0x000000,
    selected_fill=0x1A1A1A,
    selected_outline=0x2E2E2E,
    selected_label=0xFFFFFF,
)
buttons.append(button_view1)  # adding this button to the buttons group
# viwe 2
button_view2 = Button(
    x=TAPS_WIDTH,
    y=0,
    width=TAPS_WIDTH,
    height=TAPS_HEIGHT,
    label="View 2",
    label_font=font,
    label_color=0xFFFFFF,
    fill_color=0x979697,
    outline_color=0x000000,
    selected_fill=0x1A1A1A,
    selected_outline=0x2E2E2E,
    selected_label=0xFFFFFF,
)
buttons.append(button_view2)  # adding this button to the buttons group
# View 3
button_view3 = Button(
    x=TAPS_WIDTH * 2,
    y=0,
    width=TAPS_WIDTH,
    height=TAPS_HEIGHT,
    label="View 3",
    label_font=font,
    label_color=0xFFFFFF,
    fill_color=0x979697,
    outline_color=0x000000,
    selected_fill=0x1A1A1A,
    selected_outline=0x2E2E2E,
    selected_label=0xFFFFFF,
)
buttons.append(button_view3)  # adding this button to the buttons group

# Add all of the main buttons to the splash Group
for b in buttons:
    splash.append(b)
# pylint: disable=global-statement
def switch_view(what_view):
    global view_live
    if what_view == 1:
        hideLayer(view2)
        hideLayer(view3)
        button_view1.selected = False
        button_view2.selected = True
        button_view3.selected = True
        showLayer(view1)
        view_live = 1
        print("View1 On")
    elif what_view == 2:
        # global icon
        hideLayer(view1)
        hideLayer(view3)
        button_view1.selected = True
        button_view2.selected = False
        button_view3.selected = True
        showLayer(view2)
        view_live = 2
        print("View2 On")
    else:
        hideLayer(view1)
        hideLayer(view2)
        button_view1.selected = True
        button_view2.selected = True
        button_view3.selected = False
        showLayer(view3)
        view_live = 3
        print("View3 On")

# Set veriables and startup states
button_view1.selected = False
button_view2.selected = True
button_view3.selected = True
showLayer(view1)
hideLayer(view2)
hideLayer(view3)
view_live = 1

# Update out Labels with display text.
text_box(feed1_label, TABS_Y, "Print values here:", 30)  # View 1
text_box(feed2_label, TABS_Y, "Print values here:", 30)  # View 2
text_box(feed3_label, TABS_Y, "Values from PyPortaln:", 30)  # View 3

board.DISPLAY.show(splash)

# ------------- Code Loop ------------- #
while True:

    try:
        io.loop()
    except (ValueError, RuntimeError) as e:
        print("Failed to get data, retrying\n", e)
        wifi.reset()
        io.reconnect()
        continue
    time.sleep(0.5)

    touch = ts.touch_point
    light = light_sensor.value

    if adt:  # Only if we have the temperature sensor
        tempC = adt.temperature
    else:  # No temperature sensor
        tempC = microcontroller.cpu.temperature

    adafruit_data.text = "Value from Temperature feed: {}".format(
        message
    )

    sensor_data.text = "Touch: {}\nLight: {}\nTemp: {:.0f}°C".format(
        touch, light, tempC
    )

    # ------------- Handle Button Press Detection  ------------- #
    if touch:  # Only do this if the screen is touched
        # loop with buttons using enumerate() to number each button group as i
        for i, b in enumerate(buttons):
            if b.contains(touch):  # Test each button to see if it was pressed
                print("button%d pressed" % i)
                if i == 0 and view_live != 1:  # only if view1 is visable
                    pyportal.play_file(soundBeep)
                    switch_view(1)
                    while ts.touch_point:
                        pass
                if i == 1 and view_live != 2:  # only if view2 is visable
                    pyportal.play_file(soundBeep)
                    switch_view(2)
                    while ts.touch_point:
                        pass
                if i == 2 and view_live != 3:  # only if view3 is visable
                    pyportal.play_file(soundBeep)
                    switch_view(3)
                    while ts.touch_point:
                        pass
