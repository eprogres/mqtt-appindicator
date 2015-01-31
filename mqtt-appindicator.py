#!/usr/bin/env python
"""
Appindicator that subscribe to mqtt broker and notify user for new messages
Please edit config file 'mqtt-appindicator.ini' to provide settings.
Example:
    [mqtt_broker]
    mqtt_server = localhost
    mqtt_port = 1883
    mqtt_topics = [("my/topic", 0), ("another/topic", 2)]
"""
__author__ = 'Artyom Alexandrov <qk4l()tem4uk.ru>'
__license__ = """Eclipse Public License - v 1.0 (http://www.eclipse.org/legal/epl-v10.html)"""

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import appindicator
import os
import pynotify
import ConfigParser
import paho.mqtt.client as paho  # pip install paho-mqtt
import threading
import sys
gtk.gdk.threads_init()

# Config
APP_NAME = 'mqtt-appindicator'
WORK_DIR = os.path.dirname(sys.argv[0]) + '/'
CONFIGFILE = WORK_DIR + APP_NAME + '.ini'
config_section = 'mqtt_broker'
icon_ok = WORK_DIR + 'icons/mqtticon.png'
icon_fail = WORK_DIR + 'icons/mqtticon-fail.png'
# Default settings
config = {'mqtt_server': 'localhost',
          'mqtt_port': 1883,
          'mqtt_topics': [("my/topic", 0), ("another/topic", 2)]}
# End Config


class MQTTIndicator:
    def __init__(self):
        # create an indicator applet
        self.ind = appindicator.Indicator('MQTT Tray', 'mqtt-messages', appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind.set_status(appindicator.STATUS_ACTIVE)
        self.ind.set_attention_icon('indicator-messages-new')
        self.set_icon(False)
        self.item = ''
        self.items_max = 10  # maximum number of items

        # create a menu
        self.menu = gtk.Menu()
        # A separator
        separator = gtk.SeparatorMenuItem()
        separator.show()
        self.menu.append(separator)
        # create items for the menu
        self.status = gtk.MenuItem('')
        self.status.show()
        self.menu.append(self.status)
        # quit menu
        btnquit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        btnquit.connect("activate", self.quit)
        btnquit.show()
        self.menu.append(btnquit)
        self.menu.show()
        self.ind.set_menu(self.menu)
        # MQTT thread
        self.t_mqtt = MQTTBroker()

    def update_status(self, msg):
        self.status.get_child().set_text(msg)

    def set_icon(self, status):
        if status is True:
            self.ind.set_icon(icon_ok)
        else:
            self.ind.set_icon(icon_fail)

    def update(self, msg=''):
        if len(self.menu) >= self.items_max + 2:
            # Remove old items
            # TODO Remove not all items in more beautiful way
            count = 1
            for i in self.menu.get_children():
                if hasattr(i, 'mqtt_msq') and count == self.items_max:
                    self.menu.remove(i)
                count += 1
        # Add new item
        self.item = gtk.MenuItem(msg)
        self.item.mqtt_msg = True
        self.item.connect("activate", self.remove_item)
        self.item.show()
        self.menu.prepend(self.item)

    def remove_item(self, item):
        self.menu.remove(item)

    def quit(self, widget, data=None):
        # Close mqtt tread
        self.t_mqtt.quit()
        gtk.main_quit()

    def main(self):
        # Start mqtt thread
        self.t_mqtt.start()
        gtk.main()


class MQTTBroker(threading.Thread):
    def __init__(self):
        super(MQTTBroker, self).__init__()
        # create a broker
        self.mqttc = paho.Client('MQTTIndicator' + str(os.getpid()))

        # define the callbacks
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_disconnect = self.on_disconnect

    def quit(self):
        self.mqttc.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        # define what happens after connection
        if rc == 0:
            msg = '[INFO] Connection successful'
            # subscribe to topics
            self.mqttc.subscribe(config['mqtt_topics'])
            gobject.idle_add(indicator.set_icon, True)
        else:
            msg = '[INFO] Connection unsuccessful. Error:' + paho.connack_string(rc)
        update_status(msg)

    def on_disconnect(self, client, userdata, rc):
        # define what happens after disconnect
        if rc != 0:
            msg = '[INFO] Unexpected disconnection. Error:' + paho.connack_string(rc)
            gobject.idle_add(indicator.set_icon, False)
            update_status(msg)

    def on_message(self, client, userdata, msg):
        # On recipt of a message create a pynotification and show it
        show_notify(msg.payload)
        gobject.idle_add(indicator.update, msg.payload)

    def run(self):
        # try to connect
        try:
            update_status("[INFO] Connecting to %s:%d" % (config['mqtt_server'], config['mqtt_port']))
            self.mqttc.connect_async(config['mqtt_server'], config['mqtt_port'], 60)
            # keep connected to broker
            self.mqttc.loop_forever()
        except Exception, e:
            update_status("Cannot connect to MQTT broker at %s:%d: %s" %
                          (config['mqtt_server'], config['mqtt_port'], str(e)))


def update_status(msg):
    show_notify(msg)
    gobject.idle_add(indicator.update_status, msg)


def show_notify(msg):
    # Show notificathion by pynotify
    n = pynotify.Notification('MQTT Notify', msg, 'file://' + icon_ok)
    n.set_urgency(pynotify.URGENCY_CRITICAL)
    n.show()


def configread(conf_file):
    """
    :param conf_file: File path to config file
    :return: Dict of data
    """
    conf_parse = ConfigParser.SafeConfigParser()
    config = {}
    try:
        conf_parse.read(conf_file)
        config['mqtt_server'] = conf_parse.get(config_section, "mqtt_server")
        config['mqtt_port'] = conf_parse.getint(config_section, "mqtt_port")
        config['mqtt_topics'] = eval("%s" % conf_parse.get(config_section, "mqtt_topics"))
    except Exception, e:
        print "Cannot open configuration at %s: %s" % (conf_file, str(e))
        sys.exit(2)
    return config


def configwrite(conf_file):
    """
    Create new config file if it does not exist
    :param conf_file: File path to config file
    :return: Boolean
    """
    conf_parse = ConfigParser.RawConfigParser()
    conf_parse.add_section(config_section)
    for key, value in config.iteritems():
        conf_parse.set(config_section, key, value)
    # Writing our configuration file to 'example.cfg'
    try:
        with open(conf_file, 'wb') as conf_file:
            conf_parse.write(conf_file)
    except Exception, e:
        print "Cannot write configuration at %s: %s" % (conf_file, str(e))


if __name__ == "__main__":
    if os.path.isfile(CONFIGFILE):
        config = configread(CONFIGFILE)
    else:
        configwrite(CONFIGFILE)

    pynotify.init("Basic")
    indicator = MQTTIndicator()
    indicator.main()
