#!/usr/bin/python2.4
# -*- coding: utf-8 -*-
#
# Univention Installer
#  installer module: default system language
#
# Copyright (C) 2004, 2005, 2006 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# Binary versions of this file provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

#
# Results of previous modules are placed in self.all_results (dictionary)
# Results of this module need to be stored in the dictionary self.result (variablename:value[,value1,value2])
#

import objects, string, time
from objects import *
from local import _

class object(content):
	def checkname(self):
		return ['locale_default']

	def profile_complete(self):
		if self.check('locale_default'):
			return False
		if self.all_results.has_key('locale_default'):
			return True
		else:
			if self.ignore('locale_default'):
				return True
			return False

	def run_profiled(self):
		if self.all_results.has_key('locale_default'):
			return {'locale_default': self.all_results['locale_default']}

	def __create_selection( self ):
		default_value=''
		self._locales=self.all_results['locales']
		dict={}

		if self.all_results.has_key('locale_default'):
			default_value=self.all_results['locale_default']
		elif hasattr( self, '_locale_default' ):
			default_value = self._locale_default

		count=0
		default_line=0
		for i in self._locales.split(" "):
			dict[i]=[i, count]

			if i == default_value:
				default_line = count
			count=count+1

		self.elements.append(radiobutton(dict,self.minY,self.minX+2,33,10, [default_line])) #3
		self.elements[3].current=default_line

	def draw( self ):
		if hasattr( self, '_locales' ):
			self._locale_default = self.elements[ 3 ].result()
			del self.elements[ 3 ]
			self.__create_selection()

		content.draw( self )

	def layout(self):
		self.elements.append(textline(_('Select your default system language:'),self.minY-1,self.minX+2)) #2

		self.__create_selection()

	def input(self,key):
		if key in [ 10, 32 ] and self.btn_next():
			return 'next'
		elif key in [ 10, 32 ] and self.btn_back():
			return 'prev'
		else:
			return self.elements[self.current].key_event(key)

	def incomplete(self):
		if string.join(self.elements[3].result(), ' ').strip(' ') == '':
			return _('Please select the default system language')
		return 0

	def helptext(self):
		return _('Default language \n \n Select a default system language.')

	def modheader(self):
		return _('Default language')

	def result(self):
		result={}
		result['locale_default']=self.elements[3].result()
		return result
