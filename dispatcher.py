# Copyright (C) 2013-2017 Jean-Francois Romang (jromang@posteo.de)
#                         Shivkumar Shivaji ()
#                         Jürgen Précour (LocutusOfPenguin@posteo.de)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import logging
import queue
from threading import Timer, Thread, Lock
from copy import deepcopy

from utilities import DisplayDgt, DispatchDgt, dispatch_queue
from dgt.api import Dgt, DgtApi
from dgt.menu import DgtMenu
from dgt.iface import DgtIface
from dgt.util import ClockIcons
from dgt.board import DgtBoard


class Dispatcher(DispatchDgt, Thread):

    """A dispatcher taking the dispatch_queue and fill dgt_queue with the commands in time."""

    def __init__(self, dgtmenu: DgtMenu, dgtboard: DgtBoard):
        super(Dispatcher, self).__init__()

        self.dgtmenu = dgtmenu
        self.dgtboard = dgtboard
        self.devices = {}
        self.maxtimer = {}
        self.maxtimer_running = {}
        self.clock_connected = {}
        self.time_factor = 1  # This is for testing the duration - remove it lateron!
        self.tasks = {}  # delayed task array

        self.display_hash = {}  # Hash value of clock's display
        self.process_lock = {}

    def register(self, dev):
        """Register new device to send DgtApi messsages."""
        devname = dev.get_name()

        logging.debug('device %s registered', devname)
        dev.old_init(self.dgtmenu.dgttranslate, self.dgtboard)  # Still needed!
        self.devices[devname] = dev
        self.maxtimer[devname] = None
        self.maxtimer_running[devname] = False
        self.clock_connected[devname] = False
        self.process_lock[devname] = Lock()
        self.tasks[devname] = []
        self.display_hash[devname] = None

    def get_prio_device(self):
        """Return the most prio registered device."""
        if 'i2c' in self.devices:
            return 'i2c'
        if 'ser' in self.devices:
            return 'ser'
        return 'web'

    def _stopped_maxtimer(self, devname: str):
        self.maxtimer_running[devname] = False
        self.dgtmenu.disable_picochess_displayed(devname)

        if self.tasks[devname]:
            logging.debug('processing delayed (%s) tasks: %s', devname, self.tasks[devname])
        else:
            logging.debug('(%s) max timer finished - returning to time display', devname)
            DisplayDgt.show(Dgt.DISPLAY_TIME(force=False, wait=True, devs={devname}))
        while self.tasks[devname]:
            logging.debug('(%s) tasks has %i members', devname, len(self.tasks[devname]))
            try:
                message = self.tasks[devname].pop(0)
            except IndexError:
                break
            with self.process_lock[devname]:
                self._process_message(message, devname)
            if self.maxtimer_running[devname]:  # run over the task list until a maxtime command was processed
                remaining = len(self.tasks[devname])
                if remaining:
                    logging.debug('(%s) tasks stopped on %i remaining members', devname, remaining)
                else:
                    logging.debug('(%s) tasks completed', devname)
                break

    def _process_message(self, message, devname: str):
        do_handle = True
        if repr(message) in (DgtApi.CLOCK_START, DgtApi.CLOCK_STOP):
            self.display_hash[devname] = None  # Cant know the clock display if command changing the running status
        else:
            if repr(message) in (DgtApi.DISPLAY_MOVE, DgtApi.DISPLAY_TEXT):
                if self.display_hash[devname] == hash(message) and not message.beep:
                    do_handle = False
                else:
                    self.display_hash[devname] = hash(message)

        if do_handle:
            logging.debug('(%s) handle DgtApi: %s', devname, message)
            if repr(message) == DgtApi.CLOCK_VERSION:
                logging.debug('(%s) clock registered', devname)
                self.clock_connected[devname] = True

            clk = (DgtApi.DISPLAY_MOVE, DgtApi.DISPLAY_TEXT, DgtApi.DISPLAY_TIME, DgtApi.CLOCK_START, DgtApi.CLOCK_STOP)
            if repr(message) in clk and not self.clock_connected[devname]:
                logging.debug('(%s) clock still not registered => ignore %s', devname, message)
                return
            if hasattr(message, 'maxtime') and message.maxtime > 0:
                if repr(message) == DgtApi.DISPLAY_TEXT:
                    if message.maxtime == 2.1:  # 2.1=picochess message
                        self.dgtmenu.enable_picochess_displayed(devname)
                    if self.dgtmenu.inside_updt_menu():
                        if message.maxtime == 0.1:  # 0.1=eBoard error
                            logging.debug('(%s) inside update menu => board errors not displayed', devname)
                            return
                        if message.maxtime == 1.1:  # 1.1=eBoard connect
                            logging.debug('(%s) inside update menu => board connect not displayed', devname)
                            return
                self.maxtimer[devname] = Timer(message.maxtime * self.time_factor, self._stopped_maxtimer, [devname])
                self.maxtimer[devname].start()
                logging.debug('(%s) showing %s for %.1f secs', devname, message, message.maxtime * self.time_factor)
                self.maxtimer_running[devname] = True
            if repr(message) == DgtApi.CLOCK_START and self.dgtmenu.inside_updt_menu():
                logging.debug('(%s) inside update menu => clock not started', devname)
                return
            # message.devs = {devname}  # on new system, we only have ONE device each message - force this!
            self.process(devname, message)
        else:
            logging.debug('(%s) hash ignore DgtApi: %s', devname, message)

    def process(self, devname, message):
        device = self.devices[devname]  # type: DgtIface

        logging.debug('(%s) handle DgtApi: %s started', devname, message)

        if False:  # switch-case
            pass
        elif isinstance(message, Dgt.DISPLAY_MOVE):
            device.display_move_on_clock(message)
        elif isinstance(message, Dgt.DISPLAY_TEXT):
            device.display_text_on_clock(message)
        elif isinstance(message, Dgt.DISPLAY_TIME):
            device.display_time_on_clock(message)
        elif isinstance(message, Dgt.LIGHT_CLEAR):
            device.clear_light_on_revelation()
        elif isinstance(message, Dgt.LIGHT_SQUARES):
            device.light_squares_on_revelation(message.uci_move)
        elif isinstance(message, Dgt.CLOCK_STOP):
            if device.clock_running:
                device.stop_clock(message.devs)
            else:
                logging.debug('(%s) clock is already stopped', ','.join(message.devs))
        elif isinstance(message, Dgt.CLOCK_START):
            device.start_clock(message.time_left, message.time_right, message.side, message.devs)
        elif isinstance(message, Dgt.CLOCK_VERSION):
            text = device.dgttranslate.text('Y21_picochess', devs=message.devs)
            text.rd = ClockIcons.DOT
            DispatchDgt.fire(text)
            DispatchDgt.fire(Dgt.DISPLAY_TIME(force=True, wait=True, devs=message.devs))
            if 'i2c' == devname:
                logging.debug('(i2c) clock found => starting the board connection')
                device.dgtboard.run()  # finally start the serial board connection - see picochess.py
            else:
                if message.main == 2:
                    device.enable_dgt_3000 = True
        else:  # switch-default
            pass
        logging.debug('(%s) handle DgtApi: %s ended', devname, message)

    def stop_maxtimer(self, devname):
        """Stop the maxtimer."""
        if self.maxtimer_running[devname]:
            self.maxtimer[devname].cancel()
            self.maxtimer[devname].join()
            self.maxtimer_running[devname] = False
            self.dgtmenu.disable_picochess_displayed(devname)

    def run(self):
        """Call by threading.Thread start() function."""
        logging.info('dispatch_queue ready')
        while True:
            # Check if we have something to display
            try:
                msg = dispatch_queue.get()
                logging.debug('received command from dispatch_queue: %s devs: %s', msg, ','.join(msg.devs))

                for devname in msg.devs:
                    if devname not in self.devices:
                        continue
                    message = deepcopy(msg)
                    if self.maxtimer_running[devname]:
                        if hasattr(message, 'wait'):
                            if message.wait:
                                self.tasks[devname].append(message)
                                logging.debug('(%s) tasks delayed: %s', devname, self.tasks[devname])
                                continue
                            else:
                                logging.debug('ignore former maxtime - dev: %s', devname)
                                self.stop_maxtimer(devname)
                                if self.tasks[devname]:
                                    logging.debug('delete following (%s) tasks: %s', devname, self.tasks[devname])
                                    self.tasks[devname] = []
                        else:
                            logging.debug('command doesnt change the clock display => (%s) max timer ignored', devname)
                    else:
                        logging.debug('(%s) max timer not running => processing command: %s', devname, message)

                    with self.process_lock[devname]:
                        self._process_message(message, devname)
            except queue.Empty:
                pass
