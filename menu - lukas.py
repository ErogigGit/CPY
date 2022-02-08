import microcontroller
import board
import time
import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_button import Button
import adafruit_touchscreen
from adafruit_display_shapes.sparkline import Sparkline
import busio
import digitalio
from analogio import AnalogIn
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager
import neopixel
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
from adafruit_display_text.label import Label
import adafruit_sdcard
import storage
import os
import gc
import adafruit_requests as requests
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi

# Import secrets
try:
    from secrets import secrets
except ImportError:
    print("Secrets not found! Please create a secrets.py file!")
    raise

# definitions
w = 480 # display width and height
h = 320

feed_name = "temperature"
temperature = 0 # stores the temperature shown on screen

helvetica = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf") # load font
dseg = bitmap_font.load_font("/fonts/DSEG7-Classic-36-r.bdf") # load font

update_interval = 3600 # how often data is logged and graphs are updated needs to be a divisor of 3600
max_hours = 72 # to avoid having more than 100 data points the number of hours logged is based on the interval
tz_c = 2 # timezone correction when requesting data
file_writes = 0

last_update = 0
prev = 0

use_sd = 0

spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.SD_CS)

# Setup SD card
try:
    sdcard = adafruit_sdcard.SDCard(spi, cs)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")
    data_dir = "/sd/data_stuff.txt"
    print(os.listdir('/sd'))
except OSError as error:
    print("No SD card. Quitting")
    raise

# PyPortal ESP32 Setup
esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets)
requests.set_socket(socket, esp)

# on board neopixel
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)

# sensor setup
i2c = busio.I2C(board.SCL, board.SDA)
try:
    sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)
except:
    sensor = microcontroller.cpu
    print("BME680 Not found, temperature will come from the microcontroller!")

# adafruit IO setup
ADAFRUIT_IO_USER = secrets['aio_username']
ADAFRUIT_IO_KEY = secrets['aio_key']
io = IO_HTTP(ADAFRUIT_IO_USER, ADAFRUIT_IO_KEY, wifi)

try:
    temperature_feed = io.get_feed("temperature")
except AdafruitIO_RequestError:
    print("Feed not found")

# touch screen setup
ts = adafruit_touchscreen.Touchscreen(
    board.TOUCH_XL,
    board.TOUCH_XR,
    board.TOUCH_YD,
    board.TOUCH_YU,
    calibration=((5200, 59000), (5800, 57000)),
    size=(w, h)
)

# helper functions

def center_text_x(label: Label):
    try:
        label.bounding_box[2]
        label.x = int(w/2 - label.bounding_box[2]/2)
    except:
        print("Couldn't center text")

def update_graph(list_in):
    graph.clear_values()
    time.sleep(1)
    print(list_in)
    if len(list_in)>1:
        for i in list_in:
            graph.add_value(i)
            list_in.remove(i) # save memory by removing them from the input list as they are added to the sparkline list
    else:
        print("Empty")
    print(graph.values())
    graph.update()

def iso_struct(iso_string): # returns a struct time object ignoring timezone and milliseconds from an iso8601 string
    if iso_string.rfind("T"): # checks if the string is a time or a datetime
        datetime = iso_string.split("T") # splits date and time
        if iso_string.rfind("+") > 0:
            tz = datetime[1].split("+")
        elif iso_string.rfind("-") > 0:
            tz = datetime[1].split("-")
        else:
            datetime[1].replace("Z", "") # removes zulu
        d = datetime[0].split("-") # list with year, month, date
        t = datetime[1].split(":") # list with hour, minute, second
        st = time.struct_time(d[0], d[1], d[2], t[0], t[1], t[2]) # turns it into a tuple
    else:
        d = iso_string.split("-") # list with year, month, date
        st = time.struct_time(d[0], d[1], d[2])
    return st

def write_to_file(to_write, path):
    try:
        open(path, "a")
    except:
        open(path, "w")
        print("Created file")
    with open(path, "a") as fp:
        fp.write(to_write)
        fp.flush()
        print("Wrote to file")

def struct_iso(tm_struct): # Returns an iso8601 string from a tuple
    try:
        year, month, day, hour, minute, second = tm_struct[0:6]
        date="%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, hour, minute, second)
        return date
    except:
        print("Error Not a struct.")

def time_delta(current_time, hours): # takes in a struct time and subtracts hours from it then returns an iso time.
    t_in = time.localtime(time.mktime(current_time) - (hours*60*60)) # https://circuitpython.readthedocs.io/en/latest/shared-bindings/time/
    return struct_iso(t_in)

def better_request(feed_name: str, params: str = f'X-AIO-Key={secrets["aio_key"]}'): # Returns data from AIO a datapoint at a time. DO NOT CHANGE DEFAULT PARAMS!
    json_url = f'https://io.adafruit.com/api/v2/{secrets["aio_username"]}/feeds/{feed_name}/data?{params}'
    val_list = []
    print(json_url)
    time.sleep(0.1)
    response = requests.get(json_url)
    response = response.json() # parses into a dictionary
    print(len(response))
    for i in response:
        val_list.append(float(i["value"]))
    print(val_list)
    return val_list, print("Done")

def hide_layer(hide_target):
    try:
        splash.remove(hide_target)
    except ValueError:
        pass

def show_layer(show_target):
    try:
        time.sleep(0.1)
        splash.append(show_target)
    except ValueError:
        pass

def set_brightness(level):
        level = max(0, min(1.0, level))
        board.DISPLAY.auto_brightness = False
        board.DISPLAY.brightness = level

def get_data_sd(delta: int, path: str, n: int): # reads data from the sd card and returns a list
    # assuming data logging n times per hour we should go back n*delta number of lines in the file
    # as long as its LESS than the number of lines in the file
    num_lines = 0
    fd = []
    f = open(path, 'r')
    for e in f:
        num_lines += 1
        fd.append(int(float(str(e.strip("\n")))))
    if n*delta < num_lines:
        return fd[0:(n*delta-1)]
    else:
        return fd[0:(num_lines)]

def get_graphlist(data_interval: int, path: str):
    if use_sd == 1: # gets data from the sd card
        return get_data_sd(data_interval+tz_c, path, int(3600/update_interval))
    elif use_sd == 0: # gets data from aio
        debug = better_request(feed_name="temperature", params=f'X-AIO-Key={secrets["aio_key"]}&start_time={time_delta(io.receive_time(), data_interval+tz_c)}&limit=72')
        return debug[0]


# add UI elements

splash = displayio.Group(max_size=10) # groups
graph_group = displayio.Group(max_size=10)
info_group = displayio.Group(max_size=10)

board.DISPLAY.show(splash) # test to see if this actually works or if the other splashes should be included in the splash one

# setup solid background
color_bitmap = displayio.Bitmap(w, h, 1) # size and number of colors
color_palette = displayio.Palette(1) # number of colors
color_palette[0] = 0x202020 # grey

graph_btn = Button(x=0, y=0, width=int(w/2), height=int(h/6), label="Graph", fill_color=0x303030, label_color=0xFFFFFF, label_font=helvetica)
info_btn = Button(x=int(w/2), y=0, width=int(w/2), height=int(h/6), label="Info", fill_color=0x303030, label_color=0xFFFFFF, label_font=helvetica)
temperature_label = Label(x=0, y=int(5*h/6), font=helvetica, text=" "*12)
time_label = Label(x=0, y=int(3*h/6), font=dseg, text=" "*12)
graph = Sparkline(width=int(w), height=int(160), max_items=144, x=0, y=int(h/6), y_min=0, y_max=40)
#image_load = displayio.OnDiskBitmap(open("/images/pcb_photo.bmp", "rb"))
#bg_image = displayio.TileGrid(image_load, pixel_shader=displayio.ColorConverter())
bg_plain = displayio.TileGrid(color_bitmap,pixel_shader=color_palette,x=0, y=0) # set the background
half_max_btn = Button(x=0, y=int(7*h/8), width=int(w/6), height=int(h/8), label="{}h".format(str(int(max_hours/3))), fill_color=0x303030, label_color=0xFFFFFF, label_font=helvetica)
max_btn = Button(x=int(w/6), y=int(7*h/8), width=int(w/6), height=int(h/8), label="{}h".format(str(max_hours)), fill_color=0x303030, label_color=0xFFFFFF, label_font=helvetica)
aio_btn = Button(x=0, y=int(6*h/8), width=int(w/6), height=int(h/8), label="AIO", fill_color=0x303030, label_color=0xFFFFFF, label_font=helvetica)
sd_btn = Button(x=int(w/6), y=int(6*h/8), width=int(w/6), height=int(h/8), label="SD", fill_color=0x303030, label_color=0xFFFFFF, label_font=helvetica)


#splash.append(bg_image) # bg image
splash.append(bg_plain) # plain bg with a single color
splash.append(graph_btn)
splash.append(info_btn)

graph_group.append(graph)
graph_group.append(half_max_btn)
graph_group.append(max_btn)
graph_group.append(sd_btn)
graph_group.append(aio_btn)

info_group.append(time_label)
info_group.append(temperature_label)

# loop

c_time = io.receive_time()

while True:
    temperature = round(sensor.temperature, 2) # read temperature
    c_time = io.receive_time()
    if time.monotonic() > prev + 30: # after roughly 30 seconds the backlight is turned off and if update_interval has elapsed data is logged and graphs are updated
        set_brightness(0)
        prev = time.monotonic()
        if int(time.mktime(c_time)) - last_update > update_interval:
            if file_writes == max_hours:
                open(data_dir, 'w').close() # clears the file after 72 hours
            else:
                write_to_file(str(temperature) + "\n", data_dir)
                file_writes += 1
            try:
                io.send_data(temperature_feed['key'], temperature, precision=2)
                print("Sent")
            except:
                print("Failed to send")
            last_update = int(time.mktime(c_time))

    p = ts.touch_point

    if p: # touch selection
        print(p)
        print("free mem:", gc.mem_free()) # debug to see free memory
        set_brightness(1) # turns the backlight on when the screen is touched
        start_time = time.monotonic()
        if graph_btn.contains(p):
            graph_btn.selected = True
            info_btn.selected = False
        elif info_btn.contains(p):
            info_btn.selected = True
            graph_btn.selected = False
        elif half_max_btn.contains(p):
            max_btn.selected = False
            half_max_btn.selected = True
            update_graph(get_graphlist(int(max_hours/3), data_dir))
            time.sleep(2)
        elif max_btn.contains(p):
            half_max_btn.selected = False
            max_btn.selected = True
            update_graph(get_graphlist(max_hours, data_dir))
            time.sleep(2)
        elif aio_btn.contains(p):
            aio_btn.selected = True
            sd_btn.selected = False
            use_sd = 0
        elif sd_btn.contains(p):
            aio_btn.selected = False
            sd_btn.selected = True
            use_sd = 1
        else:
            max_btn.selected = False
            half_max_btn.selected = False
            sd_btn.selected = False
            aio_btn.selected = False
            graph_btn.selected = False
            info_btn.selected = False

    if info_btn.selected == True: # selection response
        hide_layer(graph_group)
        show_layer(info_group)
        center_text_x(time_label)
        center_text_x(temperature_label)
        temperature_label.text = "{}°C".format(str(temperature))
        time_label.text = "{}:{}".format(str(c_time[3]), str(c_time[4]))
    elif graph_btn.selected == True:
        show_layer(graph_group)
        hide_layer(info_group)
    else:
        hide_layer(graph_group)
        hide_layer(info_group)# Skriv din kod här :-)
