#!/usr/bin/python3
# -*- coding: utf-8 -*-
from tkinter import constants as TkC
import os
import subprocess
import sys
from tkinter import Tk, Frame, Button, Label, PhotoImage, Scrollbar, Text
from math import sqrt, floor, ceil
import threading
import yaml

class IconCache():
    icons = {}
    path = ''
    extList = ['.png', '.gif']
    pathList = [
        '/ico/',
        # '/png/96/',
        # '/png/72/',
        '/png/48/',
        '/png/24/'
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
    def __init__(self, command, frame):
        self.command = command
        self.frame = frame
        self.main_thread = threading.Thread(target=self.start)
        self.path = os.path.dirname(os.path.realpath(sys.argv[0]))
    def run(self):
        self.main_thread.start()
    def start(self):
        print("Thread: start")
        p = subprocess.Popen(self.command, stdout=subprocess.PIPE, bufsize=1, text=True)
        while p.poll() is None:
            msg = p.stdout.readline().strip() # read a line from the process output
            if msg:
                print(msg)
        print("Thread: end")
    def stop(self):
        subprocess.call(['killall', '-9', self.command[0]])


    def trigger(self, command=None):
        text = Text(self.frame)
        text.pack(side='left', fill='both', expand=True)

        scrollbar = Scrollbar(self.frame)
        scrollbar.pack(side='right', fill='y')

        text['yscrollcommand'] = scrollbar.set
        scrollbar['command'] = text.yview

        old_stdout = sys.stdout
        sys.stdout = Redirect(text)

        button = FlatButton(self.frame, text='TEST', command=self.run, image=self.iconCache.get_icon("monitor"),)
        button.pack()
        button2 = FlatButton(self.frame, text='Stop', command=self.stop, image=self.iconCache.get_icon("sign-error"),)
        button2.pack()
        if command is not None:
          closeButton = FlatButton(self.frame, text='Close', command=command, image=self.iconCache.get_icon("sign-left"),)
          closeButton.pack()

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
            actionWindow.destroy()
            self.destroy_all()
            self.show_top()

        p1 = Runner(command.split(), actionWindow)
        p1.trigger(command=lambda  self=self, actionWindow=actionWindow: destroy(self, actionWindow))

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
    root.geometry("{}x{}".format(800,480))
    root.wm_title('PiMenu')
    if len(sys.argv) > 1 and sys.argv[1] == 'fs':
        root.wm_attributes('-fullscreen', True)
    PiMenu(root)
    root.mainloop()


if __name__ == '__main__':
    main()
