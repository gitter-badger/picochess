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

from chess import Board
from utilities import DisplayDgt
from dgt.util import ClockSide
from dgt.translate import DgtTranslate
from dgt.board import DgtBoard


class DgtIface(DisplayDgt):

    """An Interface class for DgtHw, DgtPi, WebVr."""

    def __init__(self):
        super(DgtIface, self).__init__()

        self.dgtboard = None
        self.dgttranslate = None

        self.clock_running = False
        self.enable_dgt_3000 = False
        self.case_res = True

    def old_init(self, dgttranslate: DgtTranslate, dgtboard: DgtBoard):
        """This function is still needed, as long we not finished."""
        self.dgttranslate = dgttranslate
        self.dgtboard = dgtboard

    def display_text_on_clock(self, message):
        """Override this function."""
        raise NotImplementedError()

    def display_move_on_clock(self, message):
        """Override this function."""
        raise NotImplementedError()

    def display_time_on_clock(self, message):
        """Override this function."""
        raise NotImplementedError()

    def light_squares_on_revelation(self, uci_move):
        """Override this function."""
        raise NotImplementedError()

    def clear_light_on_revelation(self):
        """Override this function."""
        raise NotImplementedError()

    def stop_clock(self, devs):
        """Override this function."""
        raise NotImplementedError()

    def _resume_clock(self, side):
        """Override this function."""
        raise NotImplementedError()

    def start_clock(self, time_left, time_right, side, devs):
        """Override this function."""
        raise NotImplementedError()

    def getName(self):
        """Override this function."""
        raise NotImplementedError()

    def get_san(self, message, is_xl=False):
        """Create a chess.board plus a text ready to display on clock."""
        bit_board = Board(message.fen, message.uci960)
        if bit_board.is_legal(message.move):
            move_text = bit_board.san(message.move)
        else:
            logging.warning('[%s] illegal move %s found - uci960: %s fen: %s', self.getName(), message.move,
                            message.uci960, message.fen)
            move_text = 'er{}' if is_xl else 'err {}'
            move_text = move_text.format(message.move.uci()[:4])

        if message.side == ClockSide.RIGHT:
            move_text = move_text.rjust(6 if is_xl else 8)
        text = self.dgttranslate.move(move_text)
        return bit_board, text
