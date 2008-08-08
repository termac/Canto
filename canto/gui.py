# -*- coding: utf-8 -*-

#Canto - ncurses RSS reader
#   Copyright (C) 2008 Jack Miller <jack@codezen.org>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License version 2 as 
#   published by the Free Software Foundation.

import os
import cfg
import curses
import utility
import re
import search
import feed
import reader
import sys
import tag

class Gui :
    def __init__(self, cfg, height, width, list, tags):
        """Gui() handles all of the display and navigation logic.
        It is based around the self.map list that contains information
        about each printed line.
        
        Each function in Gui() can be tied to a key in Cfg()'s key_list
        unless it's private. As such, all functions that shouldn't
        be called by the user are prefixed with __. Key() and alarm()
        are exceptions, being called by Cfg()."""

        self.cfg = cfg
        self.lines = 0
        self.height = height
        self.width = width
        self.window_list = []
        self.map = []
        self.selected = 0
        self.items = 0
        self.offset = 0

        self.list = tags
        for t in self.list :
            if len(t):
                t[0].select()
                break
        else:
            raise IndexError

        self.cfg.key_handlers.append(self)
        self.refresh(self.height, self.width)

    def refresh(self, height=0, width=0):
        """Recreate all windows and recalculate map to fit the
        new size of the terminal."""

        if height and width :
            self.height, self.width = height, width
        self.window_list = [curses.newwin(self.height + 1, \
                    self.width / self.cfg.columns, 0, \
                    (self.width / self.cfg.columns) * i) for i in range(0, self.cfg.columns)]

        for window in self.window_list:
            window.bkgdset(curses.color_pair(1))
        self.lines = self.cfg.columns * self.height
        self.__map_items()

    def __map_filter(self, i,j,row):
        """Map filter takes self.list[i][j] and returns a tuple
        for use in map. If the item shouldn't be visible, it returns
        None to be filtered out in __map_items."""

        if self.list[i].collapsed and j != 0:
            return None
        f = self.list[i][j].print_item
        l = f(self.list[i], row[0], self) - row[0]
        if not l :
            return None
        r = (i,j,row[0],l,f)
        row[0] += l
        return r

    def __map_items(self, d = 1):
        """Refresh self.map, and (by default) redraw the items. If
        necessary (d = 0), drawing can be foregone when mapping causes
        a drastic change in item order (i.e. collapsing)"""

        row = [0]
        self.map = filter(lambda x: x != None, 
                [self.__map_filter(i, j, row) for i in range(len(self.list)) for j in range(len(self.list[i]))])
        self.items = len(self.map) - 1
        if d:
            self.draw_elements()

    def key(self, t):
        """A function dispatcher based on a key from key_list."""
        if self.cfg.key_list.has_key(t) and self.cfg.key_list[t] :
            f = getattr(self, self.cfg.key_list[t], None)
            if f and not f():
                self.draw_elements()

    def help(self):
        """Help() will silent fork the canto man page."""
        utility.silentfork("man canto", 1)
        self.cfg.alarm()
        self.cfg.refresh()

    def alarm(self, listobj):
        """Rebuild map, attempt to change self.selected to 
        persist with the the same object."""

        j,k,r,l,f = self.map[self.selected]
        selected = self.list[j][k]

        self.unselect()
        for t in self.list:
            t.clear()
            t.extend(listobj)
        self.__map_items(0) 

        r = self.list[j].search_stories(selected)
        if r != -1  :
            self.selected = 0
            while self.map[self.selected][0:2] != (j,r):
                self.selected += 1
            self.select()
        else:
            self.__select_topoftag(j)

        self.cfg.key_handlers[-1].draw_elements()
   
    def __select_topoftag(self, j=0):
        """Select the first item in a tag, useful if the 
        selected story no longer exists, or if the tag
        is collapsed."""

        self.selected = 0
        while self.map[self.selected][0] != j:
            self.selected += 1
        self.select()

    def __check_scroll(self) :
        """Change offset to keep cursor visible."""
        i,j,r,l,f = self.map[self.selected]
        
        if r < self.offset :
            self.offset = r
            return 1

        if r + l > self.lines + self.offset :
            self.offset = r + l - self.lines
            return 1
        return 0

    def draw_elements(self):
        """Actually print to the ncurses screen each of
        the visible items, then provoke a screen update."""

        self.__check_scroll()
        row = -1 * self.offset
        for i,j,r,l,f in self.map :
            if r + l > self.offset :
                if r > self.lines + self.offset :
                    break
                f(self.list[i], row, self)
            row += l
        
        for i in range(len(self.window_list)) :
            if i * self.height > row:
                self.window_list[i].clear()
            else:
                self.window_list[i].clrtobot()
            self.window_list[i].noutrefresh()
        curses.doupdate()

    def __change_item(self, val):
        self.unselect()
        self.selected += val
        self.select()

    def next_item(self):
        if self.selected < self.items :
            self.__change_item(1)

    def prev_item(self):
        if self.selected > 0:
            self.__change_item(-1)

    def prev_tag(self) :
        self.unselect()
        j,k,r,l,f = self.map[self.selected]

        if j == 0:
            self.selected = 0
        else:
            while 1:
                self.selected -= 1
                j2,k2,r2,l2,f2 = self.map[self.selected]
                if j2 < j and k2 == 0 :
                    break

        self.select()

    def next_tag(self) :
        j,k,r,l,f = self.map[self.selected]

        if j != len(self.list) - 1  :
            self.unselect()

            while 1:
                self.selected += 1
                j2,k2,r2,l2,f2 = self.map[self.selected]
                if j2 > j :
                    break

            self.offset = min(r2,max(0,self.map[-1][2] + self.map[-1][3] - self.lines))
            self.select()

    def just_read(self):
        # Added for binding
        j,k,r,l,f = self.map[self.selected]
        self.list[j].set_read(k)

    def just_unread(self):
        # Added for binding.
        j,k,r,l,f = self.map[self.selected]
        self.list[j].set_unread(k)

    def goto(self) :
        """Simple item wrapper around Cfg().goto()."""
        j,k,r,l,f = self.map[self.selected]
        self.list[j].set_read(k)
        self.draw_elements()
        self.cfg.goto(self.list[j][k]["link"])

    def reader(self) :
        """Instantiate the reader."""
        j,k,r,l,f = self.map[self.selected]
        self.list[j].set_read(k)
        reader.Reader(self.list[j][k], self.height, self.width, self.cfg)
        return 1

    def inline_search(self):
        search.Search(self.cfg, " Inline Search ", \
                self.__do_inline_search, self.height, self.width, self.cfg.log)
        return 1

    def search(self):
        search.Search(self.cfg, " Collect Search ", \
                self.__do_search, self.height, self.width, self.cfg.log)
        return 1

    def __do_search(self, s) :
        if s:
            items = [y for x in self.list for y in x if s.match(y["title"])]
            if items :
                Gui(self.cfg, self.height, self.width, items, [tag.Tag("*")])

    def __do_inline_search(self, s) :
        if s:
            for t in self.list:
                for story in t:
                    if s.match(story["title"]):
                        story.mark()
                    else:
                        story.unmark()
        self.draw_elements()

    def __select_if_marked(self, newcursor) :
        j,k,r,l,f = self.map[newcursor]
        if self.list[j][k].marked() :
            self.selected = newcursor
            self.select()
            return 1
        return 0

    def next_mark(self) :
        self.unselect()
        newcursor = self.selected + 1
        while newcursor < self.items :
            if self.__select_if_marked(newcursor):
                return
            newcursor += 1
        self.select()

    def prev_mark(self) :
        self.unselect()
        newcursor = self.selected - 1
        while newcursor > 0:
            if self.__select_if_marked(newcursor):
                return
            newcursor -= 1
        self.select()

    def toggle_mark(self):
        j,k,r,l,f = self.map[self.selected]
        if self.list[j][k].marked() :
            self.list[j][k].unmark()
        else:
            self.list[j][k].mark()

    def toggle_collapse_tag(self):
        j,k,r,l,f = self.map[self.selected]
        self.list[j].collapsed = not self.list[j].collapsed
        self.unselect()
        self.__map_items(0)
        self.__select_topoftag(j)

    def __collapse_all(self, c):
        j,k,r,l,f = self.map[self.selected]
        for t in self.list:
            t.collapsed = c
        self.unselect()
        self.__map_items(0)
        self.__select_topoftag(j)

    def set_collapse_all(self):
        self.__collapse_all(1)

    def unset_collapse_all(self):
        self.__collapse_all(0)

    def force_update(self):
        self.cfg.log("Forcing update\n")
        for f in self.cfg.feeds :
            f.time = 1
        self.cfg.alarm()

    def tag_read(self):
        self.list[self.map[self.selected][0]].all_read()

    def all_read(self):
        for t in self.list:
            t.all_read()

    def tag_unread(self):
        self.list[self.map[self.selected][0]].all_unread()

    def all_unread(self):
        for t in self.list :
            t.all_unread()

    def __change_select(self, val):
        j,k,r,l,f = self.map[self.selected]
        if val == 0 :
            self.list[j][k].unselect()
        else:
            self.list[j][k].select()

    def unselect(self) :
        self.__change_select(0)

    def select(self) :
        self.__change_select(1)

    def quit(self):
        self.cfg.pop_handler()
        return 1
