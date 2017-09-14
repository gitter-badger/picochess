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
from threading import Lock

from utilities import hms_time
from dgt.iface import DgtIface
from dgt.util import ClockIcons, ClockSide, DgtClk, DgtCmd
from dgt.translate import DgtTranslate
from dgt.board import DgtBoard


class DgtHw(DgtIface):

    """Handle the DgtXL/3000 communication."""

    def __init__(self):
        super(DgtHw, self).__init__()

        self.lib_lock = Lock()

    def _display_on_dgt_xl(self, text: str, beep=False, left_icons=ClockIcons.NONE, right_icons=ClockIcons.NONE):
        text = text.ljust(6)
        if len(text) > 6:
            logging.warning('(ser) clock message too long [%s]', text)
        logging.debug('[%s]', text)
        with self.lib_lock:
            res = self.dgtboard.set_text_xl(text, 0x03 if beep else 0x00, left_icons, right_icons)
            if not res:
                logging.warning('SetText() returned error %i', res)
            return res

    def _display_on_dgt_3000(self, text: str, beep=False):
        text = text.ljust(8)
        if len(text) > 8:
            logging.warning('(ser) clock message too long [%s]', text)
        logging.debug('[%s]', text)
        text = bytes(text, 'utf-8')
        with self.lib_lock:

            res = self.dgtboard.set_text_3k(text, 0x03 if beep else 0x00)
            if not res:
                logging.warning('SetText() returned error %i', res)
            return res

    def display_text_on_clock(self, message):
        """Display a text on the dgtxl/3k."""
        display_m = self.enable_dgt_3000 and not self.dgtboard.use_revelation_leds
        text = message.m if display_m else message.s
        if text is None:
            text = message.l if display_m else message.m
        if self.getName() not in message.devs:
            logging.debug('ignored %s - devs: %s', text, message.devs)
            return True
        left_icons = message.ld if hasattr(message, 'ld') else ClockIcons.NONE
        right_icons = message.rd if hasattr(message, 'rd') else ClockIcons.NONE

        if display_m:
            return self._display_on_dgt_3000(text, message.beep)
        else:
            return self._display_on_dgt_xl(text, message.beep, left_icons, right_icons)

    def display_move_on_clock(self, message):
        """Display a move on the dgtxl/3k."""
        display_m = self.enable_dgt_3000 and not self.dgtboard.use_revelation_leds
        if display_m:
            bit_board, text = self.get_san(message)
        else:
            text = message.move.uci()
            if message.side == ClockSide.RIGHT:
                text = text[:2].rjust(3) + text[2:].rjust(3)
            else:
                text = text[:2].ljust(3) + text[2:].ljust(3)
        if self.getName() not in message.devs:
            logging.debug('ignored %s - devs: %s', text, message.devs)
            return True
        if display_m:
            return self._display_on_dgt_3000(text, message.beep)
        else:
            left_icons = message.ld if hasattr(message, 'ld') else ClockIcons.NONE
            right_icons = message.rd if hasattr(message, 'rd') else ClockIcons.NONE
            return self._display_on_dgt_xl(text, message.beep, left_icons, right_icons)

    def display_time_on_clock(self, message):
        """Display the time on the dgtxl/3k."""
        if self.getName() not in message.devs:
            logging.debug('ignored endText - devs: %s', message.devs)
            return True
        if self.clock_running or message.force:
            with self.lib_lock:
                if self.dgtboard.l_time >= 3600 * 10 or self.dgtboard.r_time >= 3600 * 10:
                    logging.debug('time values not set - abort function')
                    return False
                else:
                    return self.dgtboard.end_text()
        else:
            logging.debug('(ser) clock isnt running - no need for endText')
            return True

    def light_squares_on_revelation(self, uci_move: str):
        """Light the Rev2 leds."""
        if self.dgtboard.use_revelation_leds:
            logging.debug('(rev) leds turned on - move: %s', uci_move)
            fr_s = (8 - int(uci_move[1])) * 8 + ord(uci_move[0]) - ord('a')
            to_s = (8 - int(uci_move[3])) * 8 + ord(uci_move[2]) - ord('a')
            self.dgtboard.write_command([DgtCmd.DGT_SET_LEDS, 0x04, 0x01, fr_s, to_s, DgtClk.DGT_CMD_CLOCK_END_MESSAGE])
        return True

    def clear_light_on_revelation(self):
        """Clear the Rev2 leds."""
        if self.dgtboard.use_revelation_leds:
            logging.debug('(rev) leds turned off')
            self.dgtboard.write_command([DgtCmd.DGT_SET_LEDS, 0x04, 0x00, 0x40, 0x40, DgtClk.DGT_CMD_CLOCK_END_MESSAGE])
        return True

    def stop_clock(self, devs: set):
        """Stop the dgtxl/3k."""
        if self.getName() not in devs:
            logging.debug('ignored stopClock - devs: %s', devs)
            return True
        logging.debug('(%s) clock sending stop time to clock l:%s r:%s', ','.join(devs),
                      hms_time(self.dgtboard.l_time), hms_time(self.dgtboard.r_time))
        return self._resume_clock(ClockSide.NONE)

    def _resume_clock(self, side: ClockSide):
        if self.dgtboard.l_time >= 3600 * 10 or self.dgtboard.r_time >= 3600 * 10:
            logging.debug('time values not set - abort function')
            return False

        l_run = r_run = 0
        if side == ClockSide.LEFT:
            l_run = 1
        if side == ClockSide.RIGHT:
            r_run = 1
        with self.lib_lock:
            l_hms = hms_time(self.dgtboard.l_time)
            r_hms = hms_time(self.dgtboard.r_time)
            res = self.dgtboard.set_and_run(l_run, l_hms[0], l_hms[1], l_hms[2], r_run, r_hms[0], r_hms[1], r_hms[2])
            if not res:
                logging.warning('finally failed %i', res)
                return False
            else:
                self.clock_running = (side != ClockSide.NONE)
            if self.dgtboard.disable_end:
                return res
            return self.dgtboard.end_text()  # this is needed for some(!) clocks

    def start_clock(self, time_left: int, time_right: int, side: ClockSide, devs: set):
        """Start the dgtxl/3k."""
        if self.getName() not in devs:
            logging.debug('ignored startClock - devs: %s', devs)
            return True
        logging.debug('(%s) clock received last time from clock l:%s r:%s', ','.join(devs),
                      hms_time(self.dgtboard.l_time), hms_time(self.dgtboard.r_time))
        self.dgtboard.l_time = time_left
        self.dgtboard.r_time = time_right
        logging.debug('(%s) clock sending start time to clock l:%s r:%s', ','.join(devs),
                      hms_time(time_left), hms_time(time_right))
        return self._resume_clock(side)

    def getName(self):
        """Get name."""
        return 'ser'
