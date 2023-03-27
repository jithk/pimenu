#!/usr/bin/python3
# -*- coding: utf-8 -*-
from tkinter import constants as TkC
import os
import subprocess
import sys
from tkinter import Tk, Frame, Button, Label, PhotoImage, Scrollbar, Text, LabelFrame, StringVar
from math import sqrt, floor, ceil
import threading
import yaml
import time

import pynmea2.pynmea2 as pynmea2

# need pip3 install tkintermapview --upgrade
import tkintermapview

kScreenWidth=800
kScreenHeight=480
kMapRefreshRate=2 # in seconds

special_actions = ['showMap']

class IconCache():
    icons = {}
    path = ''
    extList = ['.png', '.gif']
    pathList = [
        '/png/96/',
        '/png/72/',
        '/png/48/',
        '/png/24/',
        '/ico/',
      ]
    path = os.path.dirname(os.path.realpath(sys.argv[0]))

    def get_icon(self, name):
        """
        Loads the given icon and keeps a reference

        :param name: string
        :return:
        """
        if name in self.icons:
            return self.icons[name]
        
        for pt in self.pathList:
            for ext in self.extList:
                ico = self.path + pt + name + ext
                if os.path.isfile(ico):
                    self.icons[name] = PhotoImage(file=ico)
                    return self.icons[name]
        
        if 'default' not in self.icons:
            self.icons['default'] = PhotoImage(file=self.path + '/ico/cancel.gif')
        return self.icons['default']

class Redirect():
    def __init__(self, widget, autoscroll=True):
        self.widget = widget
        self.autoscroll = autoscroll
    def write(self, text):
        self.widget.insert('end', text)
        if self.autoscroll:
            self.widget.see("end")  # autoscroll
    def flush(self):
        None

class FlatButton(Button):
    def __init__(self, master=None, cnf=None, **kw):
        Button.__init__(self, master, cnf, **kw)

        self.config(
            compound=TkC.TOP,
            relief=TkC.FLAT,
            bd=0,
            bg="#b91d47",  # dark-red
            fg="white",
            activebackground="#b91d47",  # dark-red
            activeforeground="white",
            highlightthickness=0
        )

    def set_color(self, color):
        self.configure(
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white"
        )


class Runner():
    icons = {}
    path = ''
    iconCache = IconCache()
    process = None
    old_sys_out = None
    def __init__(self, command, frame, bg=None, map_widget=None):
        self.command = command
        self.frame = frame
        self.main_thread = threading.Thread(target=self.start)
        self.path = os.path.dirname(os.path.realpath(sys.argv[0]))
        self.bg=bg
        self.map_widget=map_widget
        self.first_marker=None
        self.last_marker=None
        self.title_var=None
    def run(self):
        self.main_thread.start()
    def start(self):
        print("Thread: start")
        self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # i = 0
        last_time = time.time()
        last_mode = 0
        while self.process.poll() is None:
            msg = self.process.stdout.readline().strip() # read a line from the process output
            if msg and 'GPGGA' not in msg:
                print(msg)
            elif 'GPGGA' in msg and self.map_widget is not None:
                nmea = pynmea2.parse(msg)
                if not nmea.is_valid:
                    continue
                gps_qual = nmea.gps_qual
                if time.time() - last_time < kMapRefreshRate and gps_qual == last_mode:
                    continue
                last_time = time.time()
                last_mode = gps_qual
                color_circle='#caf0f8'
                color_outside='#ff006e'
                title=None
                colors_map = {
                    1:('#ff006e', 'SPP'), # SPP
                    2:('#fb5607', 'DGPS'),
                    4:('#06d6a0', 'RTK Fixed'),
                    5:('#3a86ff', 'RTK Float'),
                    6:('#6d6875', 'DR'),
                }
                if gps_qual in colors_map.keys():
                    color_outside,title = colors_map[gps_qual]
                marker = self.map_widget.set_marker(nmea.latitude, nmea.longitude, marker_color_circle=color_circle, marker_color_outside=color_outside)
                self.map_widget.set_position(nmea.latitude, nmea.longitude)
                if self.title_var is not None and title is not None:
                    self.title_var.set(title)
                if self.first_marker is None:
                    self.first_marker = marker
                elif self.last_marker is None:
                    self.last_marker = marker
                if self.last_marker is not None:
                    self.last_marker.delete()
                    self.last_marker = marker
                # print("Done {}".format(i))
                # i += 1
        print("Thread: end")
        self.process = None
    def stop(self):
        sys.stdout = self.old_sys_out
        if self.process is not None:
            self.process.kill()
        # self.join()

    def trigger(self, map_widget=None, title_var=None):
        if map_widget is None:
            text = Text(self.frame)
        else:
            text = Text(self.frame, height=7, bg=self.bg)
        text.pack(side='left', fill='x', expand=True)

        scrollbar = Scrollbar(self.frame)
        scrollbar.pack(side='right', fill='y')

        text['yscrollcommand'] = scrollbar.set
        scrollbar['command'] = text.yview

        self.old_sys_out = sys.stdout
        sys.stdout = Redirect(text)
        self.map_widget = map_widget
        self.title_var = title_var
        self.run()

    def join(self):
        self.main_thread.join()

class PiMenu(Frame):
    framestack = []
    icons = {}
    path = ''
    lastinit = 0
    iconCache = IconCache()

    def __init__(self, parent):
        Frame.__init__(self, parent, background="white")
        self.parent = parent
        self.pack(fill=TkC.BOTH, expand=1)

        self.path = os.path.dirname(os.path.realpath(sys.argv[0]))
        self.initialize()

    def initialize(self):
        """
        (re)load the the items from the yaml configuration and (re)init
        the whole menu system

        :return: None
        """
        with open(self.path + '/pimenu.yaml', 'r') as f:
            doc = yaml.load(f)
        self.lastinit = os.path.getmtime(self.path + '/pimenu.yaml')

        if len(self.framestack):
            self.destroy_all()
            self.destroy_top()

        self.show_items(doc)

    def has_config_changed(self):
        """
        Checks if the configuration has been changed since last loading

        :return: Boolean
        """
        return self.lastinit != os.path.getmtime(self.path + '/pimenu.yaml')

    def show_items(self, items, upper=None):
        """
        Creates a new page on the stack, automatically adds a back button when there are
        pages on the stack already

        :param items: list the items to display
        :param upper: list previous levels' ids
        :return: None
        """
        if upper is None:
            upper = []
        num = 0

        # create a new frame
        wrap = Frame(self, bg="black")

        if len(self.framestack):
            # when there were previous frames, hide the top one and add a back button for the new one
            self.hide_top()
            back = FlatButton(
                wrap,
                text='back…',
                image=self.iconCache.get_icon("arrow.left"),
                command=self.go_back,
            )
            back.set_color("#00a300")  # green
            back.grid(row=0, column=0, padx=1, pady=1, sticky=TkC.W + TkC.E + TkC.N + TkC.S)
            num += 1

        # add the new frame to the stack and display it
        self.framestack.append(wrap)
        self.show_top()

        # calculate tile distribution
        allitems = len(items) + num
        rows = floor(sqrt(allitems))
        cols = ceil(allitems / rows)

        # make cells autoscale
        for x in range(int(cols)):
            wrap.columnconfigure(x, weight=1)
        for y in range(int(rows)):
            wrap.rowconfigure(y, weight=1)

        # display all given buttons
        for item in items:
            act = upper + [item['name']]
            command = act
            label = item['label']
            if 'command' in item:
                command = item['command']

            if 'icon' in item:
                image = self.iconCache.get_icon(item['icon'])
            else:
                image = self.iconCache.get_icon('scrabble.' + item['label'][0:1].lower())

            btn = FlatButton(
                wrap,
                text=item['label'],
                image=image
            )

            if 'items' in item:
                # this is a deeper level
                btn.configure(command=lambda act=act, item=item: self.show_items(item['items'], act),
                              text=item['label'] + '…')
                btn.set_color("#2b5797")  # dark-blue
            elif item['name'] in special_actions:
                btn.configure(command=lambda item=item: self.do_special_action(item), )
            else:
                # this is an action
                btn.configure(command=lambda item=item: self.go_action(item), )

            if 'color' in item:
                btn.set_color(item['color'])

            # add buton to the grid
            btn.grid(
                row=int(floor(num / cols)),
                column=int(num % cols),
                padx=1,
                pady=1,
                sticky=TkC.W + TkC.E + TkC.N + TkC.S
            )
            num += 1

    def hide_top(self):
        """
        hide the top page
        :return:
        """
        self.framestack[len(self.framestack) - 1].pack_forget()

    def show_top(self):
        """
        show the top page
        :return:
        """
        self.framestack[len(self.framestack) - 1].pack(fill=TkC.BOTH, expand=1)

    def destroy_top(self):
        """
        destroy the top page
        :return:
        """
        self.framestack[len(self.framestack) - 1].destroy()
        self.framestack.pop()

    def destroy_all(self):
        """
        destroy all pages except the first aka. go back to start
        :return:
        """
        while len(self.framestack) > 1:
            self.destroy_top()

    def do_special_action(self, item):
        # hide the menu and show a delay screen
        self.hide_top()
        command = item['name']
        label = item['label']
        color = "#2b5797"
        if 'command' in item:
            command = item['command']
        actionWindow = Frame(self, bg=color)
        actionWindow.pack(fill=TkC.BOTH, expand=1)
        labelFrame = LabelFrame(actionWindow, borderwidth=0, border=0, height=1, bg=color)
        p1 = Runner(command.split(), labelFrame, bg=color)
        def destroy(self, actionWindow):
            p1.stop()
            # remove actionWindow screen and show menu again
            actionWindow.destroy()
            self.destroy_all()
            self.show_top()
        
        title_var = StringVar(value=label)
        label = Label(labelFrame, height=1, textvariable=title_var, fg="white", bg=color, font="Sans 30")
        label.pack(side='left')

        backButton = FlatButton(labelFrame, text='Close', command=lambda  self=self, actionWindow=actionWindow: destroy(self, actionWindow),
                                 image=self.iconCache.get_icon("sign-left"))
        backButton.pack(side='right')
        labelFrame.pack(side='top', fill=TkC.X, expand=1)
        map_widget = tkintermapview.TkinterMapView(actionWindow, corner_radius=0, width=kScreenWidth, height=int(kScreenHeight*.8))
        map_widget.pack(side='left',fill=TkC.BOTH, expand=1)
        map_widget.set_zoom(16)
        self.parent.update()

        p1.trigger(map_widget=map_widget, title_var=title_var)

        return

    def go_action(self, item):
        """
        execute the action script
        :param actions:
        :return:
        """
        command = item['name']
        label = item['label']
        color = "#2b5797"
        if 'color' in item:
            color = item['color']
        if 'command' in item:
            command = item['command']
        # hide the menu and show a delay screen
        self.hide_top()
        actionWindow = Frame(self, bg=color)
        actionWindow.pack(fill=TkC.BOTH, expand=1)
        label = Label(actionWindow, text=label, fg="white", bg=color, font="Sans 30")
        label.pack(fill=TkC.BOTH, expand=1)
        self.parent.update()

        def destroy(self, actionWindow):
            # remove actionWindow screen and show menu again
            p1.stop()
            actionWindow.destroy()
            self.destroy_all()
            self.show_top()

        p1 = Runner(command.split(), actionWindow, bg=color)

        backButton = FlatButton(actionWindow, text='Close', command=lambda  self=self, actionWindow=actionWindow: destroy(self, actionWindow),
                                 image=self.iconCache.get_icon("sign-left"))
        backButton.pack(side='right')
        p1.trigger()

    def go_back(self):
        """
        destroy the current frame and reshow the one below, except when the config has changed
        then reinitialize everything
        :return:
        """
        if self.has_config_changed():
            self.initialize()
        else:
            self.destroy_top()
            self.show_top()


def main():
    root = Tk()
    root.geometry("{}x{}".format(kScreenWidth,kScreenHeight))
    root.wm_title('PiMenu')
    if len(sys.argv) > 1 and sys.argv[1] == 'fs':
        root.wm_attributes('-fullscreen', True)
    PiMenu(root)
    root.mainloop()


if __name__ == '__main__':
    main()
