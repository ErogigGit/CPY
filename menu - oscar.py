import time
import board
import microcontroller
import displayio
import busio
from analogio import AnalogIn
import adafruit_adt7410
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_button import Button
import adafruit_touchscreen
from adafruit_pyportal import PyPortal

import random

from adafruit_display_shapes.sparkline import Sparkline

import adafruit_requests as requests

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


# ------------- Inputs and Outputs Setup ------------- #
try:  # attempt to init. the temperature sensor
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
    adt.high_resolution = True
except ValueError:
    # Did not find ADT7410. Probably running on Titano or Pynt
    adt = None

# init. the light sensor
light_sensor = AnalogIn(board.LIGHT)

WHITE = 0xffffff
RED = 0xff0000
YELLOW = 0xffff00
GREEN = 0x00ff00
BLUE = 0x0000ff
PURPLE = 0xff00ff
BLACK = 0x000000


# ------------- Other Helper Functions------------- #
# Helper for cycling through a number set of 1 to x.
def numberUP(num, max_val):
    num += 1
    if num <= max_val:
        return num
    else:
        return 1

# ------------- Screen Setup ------------- #
pyportal = PyPortal()
display = board.DISPLAY
display.rotation = 270

# Backlight function
# Value between 0 and 1 where 0 is OFF, 0.5 is 50% and 1 is 100% brightness.
def set_backlight(val):
    val = max(0, min(1.0, val))
    board.DISPLAY.auto_brightness = False
    board.DISPLAY.brightness = val

# Set the Backlight
set_backlight(0.3)



# Touchscreen setup
# ------Rotate 270:
screen_width = 240
screen_height = 320
ts = adafruit_touchscreen.Touchscreen(board.TOUCH_YD, board.TOUCH_YU,
                                      board.TOUCH_XR, board.TOUCH_XL,
                                      calibration=((5200, 59000),
                                                   (5800, 57000)),
                                      size=(screen_width, screen_height))


# Baseline size of the sparkline chart, in pixels.
chart_width = 240
chart_height = 100


# sparkline1 uses a vertical y range between 0 to 10 and will contain a
# maximum of 40 items
sparkline1 = Sparkline(
    width=chart_width, height=chart_height, max_items=40, y_min=0, y_max=10, x=0, y=screen_height-chart_height
)
sparkline2 = Sparkline(
    width=chart_width, height=chart_height, max_items=40, y_min=0, y_max=10, x=0, y=screen_height-chart_height
)

# ------------- Display Groups ------------- #
splash = displayio.Group(max_size=15)  # The Main Display Group
view1 = displayio.Group(max_size=15)  # Group for View 1 objects
view2 = displayio.Group(max_size=15)  # Group for View 2 objects
view3 = displayio.Group(max_size=15)  # Group for View 3 objects



# Create a group to hold the sparkline and append the sparkline into the
# group (my_group)
#
# Note: In cases where display elements will overlap, then the order the elements
# are added to the group will set which is on top.  Latter elements are displayed
# on top of former elemtns.


# add the sparkline into my_group
view1.append(sparkline1)
view2.append(sparkline2)



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

# Display an image until the loop starts
pyportal.set_background('/images/loading.bmp')


bg_group = displayio.Group(max_size=1)
splash.append(bg_group)


icon_group = displayio.Group(max_size=1)
icon_group.x = 180
icon_group.y = 120
icon_group.scale = 1
view2.append(icon_group)

# This will handel switching Images and Icons
def set_image(group, filename):
    """Set the image file for a given goup for display.
    This is most useful for Icons or image slideshows.
        :param group: The chosen group
        :param filename: The filename of the chosen image
    """
    print("Set image to ", filename)
    if group:
        group.pop()

    if not filename:
        return  # we're done, no icon desired

    image_file = open(filename, "rb")
    image = displayio.OnDiskBitmap(image_file)
    try:
        image_sprite = displayio.TileGrid(image, pixel_shader=displayio.ColorConverter())
    except TypeError:
        image_sprite = displayio.TileGrid(image, pixel_shader=displayio.ColorConverter(),
                                          position=(0, 0))
    group.append(image_sprite)

set_image(bg_group, "/images/BGimage.bmp")

# ---------- Text Boxes ------------- #
# Set the font and preload letters
font = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf")
font.load_glyphs(b'abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()')

# Default Label styling:
TABS_X = 5
TABS_Y = 50

# Text Label Objects
feed1_label = Label(font, text="Data1", color=0xE39300, max_glyphs=200)
feed1_label.x = TABS_X
feed1_label.y = TABS_Y
view1.append(feed1_label)

feed2_label = Label(font, text="Data2", color=0xE39300, max_glyphs=200)
feed2_label.x = TABS_X
feed2_label.y = TABS_Y
view2.append(feed2_label)

sensors_label = Label(font, text="Data View", color=0xE39300, max_glyphs=200)
sensors_label.x = TABS_X
sensors_label.y = TABS_Y
view3.append(sensors_label)

sensor_data = Label(font, text="Data View", color=0xE39300, max_glyphs=100)
sensor_data.x = TABS_X+15
sensor_data.y = 170
view3.append(sensor_data)


text_hight = Label(font, text="M", color=0x03AD31, max_glyphs=10)
# return a reformatted string with word wrapping using PyPortal.wrap_nicely
def text_box(target, top, string, max_chars):
    text = pyportal.wrap_nicely(string, max_chars)
    new_text = ""
    test = ""
    for w in text:
        new_text += '\n'+w
        test += 'M\n'
    text_hight.text = test  # Odd things happen without this
    glyph_box = text_hight.bounding_box
    target.text = ""  # Odd things happen without this
    target.y = int(glyph_box[3]/2)+top
    target.text = new_text

# ---------- Display Buttons ------------- #
# Default button styling:
BUTTON_HEIGHT = 40
BUTTON_WIDTH = 80

# We want three buttons across the top of the screen
TAPS_HEIGHT = 40
TAPS_WIDTH = int(screen_width/3)
TAPS_Y = 0


# This group will make it easy for us to read a button press later.
buttons = []

# Main User Interface Buttons
button_view1 = Button(x=0, y=0,
                      width=TAPS_WIDTH, height=TAPS_HEIGHT,
                      label="Data1", label_font=font, label_color=0xff7e00,
                      fill_color=0x5c5b5c, outline_color=0x767676,
                      selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                      selected_label=0x525252)
buttons.append(button_view1)  # adding this button to the buttons group

button_view2 = Button(x=TAPS_WIDTH, y=0,
                      width=TAPS_WIDTH, height=TAPS_HEIGHT,
                      label="Data2", label_font=font, label_color=0xff7e00,
                      fill_color=0x5c5b5c, outline_color=0x767676,
                      selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                      selected_label=0x525252)
buttons.append(button_view2)  # adding this button to the buttons group

button_view3 = Button(x=TAPS_WIDTH*2, y=0,
                      width=TAPS_WIDTH, height=TAPS_HEIGHT,
                      label="Live", label_font=font, label_color=0xff7e00,
                      fill_color=0x5c5b5c, outline_color=0x767676,
                      selected_fill=0x1a1a1a, selected_outline=0x2e2e2e,
                      selected_label=0x525252)
buttons.append(button_view3)  # adding this button to the buttons group


# Add all of the main buttons to the splash Group
for b in buttons:
    splash.append(b.group)




#pylint: disable=global-statement
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
#pylint: enable=global-statement

# Set veriables and startup states
button_view1.selected = False
button_view2.selected = True
button_view3.selected = True
showLayer(view1)
hideLayer(view2)
hideLayer(view3)

view_live = 1
button_mode = 1
switch_state = 0


# Update out Labels with display text.


text_box(sensors_label, TABS_Y, "This screen can display sensor readings.", 28)

board.DISPLAY.show(splash)

def dataIO(feed_name: str, params: str = f'X-AIO-Key={secrets["aio_key"]}'): # Returns data from AIO a datapoint at a time. DO NOT CHANGE DEFAULT PARAMS!
    json_url = f'https://io.adafruit.com/api/v2/{secrets["aio_username"]}/feeds/{feed_name}/data?{params}'
    IOdata = []
    print(json_url)
    time.sleep(0.1)
    response = requests.get(json_url)
    response = response.json() # parses into a dictionary
    print(len(response))
    for i in response:
        IOdata.append(float(i["value"]))
    print(IOdata)
    return IOdata, print("Done")




# ------------- Code Loop ------------- #
while True:
    touch = ts.touch_point
    light = light_sensor.value

    if adt:  # Only if we have the temperature sensor
        tempC = adt.temperature
    else:  # No temperature sensor
        tempC = microcontroller.cpu.temperature

    tempF = tempC * 1.8 + 32
    sensor_data.text = 'Light: {}\n Temp: {:.0f}Â°F'.format(light, tempF)

    # ------------- Handle Button Press Detection  ------------- #
    if touch:  # Only do this if the screen is touched
        # loop with buttons using enumerate() to number each button group as i
        for i, b in enumerate(buttons):
            if b.contains(touch):  # Test each button to see if it was pressed
                print('button%d pressed' % i)
                if i == 0 and view_live != 1:  # only if view1 is visable
                    switch_view(1)
                    while ts.touch_point:
                        pass
                if i == 1 and view_live != 2:  # only if view2 is visable
                    switch_view(2)
                    while ts.touch_point:
                        pass


                if i == 2 and view_live != 3:  # only if view3 is visable
                    switch_view(3)
                    while ts.touch_point:
                        pass



    # Sparkline

    # turn off the auto_refresh of the display while modifying the sparkline
    display.auto_refresh = False

    # add_value: add a new value to a sparkline
    # Note: The y-range for mySparkline1 is set to 0 to 10, so all these random
    # values (between 0 and 10) will fit within the visible range of this sparkline
    sparkline1.add_value(random.uniform(0, 10))
    sparkline2.add_value(random.uniform(0, 10))

    # turn the display auto_refresh back on
    display.auto_refresh = True
