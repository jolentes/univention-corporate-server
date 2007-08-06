#!/usr/bin/python2.4
# -*- coding: utf-8 -*-
#
# Univention Installer
#  installer module: security settings
#
# Copyright (C) 2007 Univention GmbH
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

import objects
from objects import *
from local import _
import string

class object(content):
	def checkname(self):
		return ['security_profile']

	def modvars(self):
		return ['security_profile']

	def mod_depends(self):
		return {'system_role': ['domaincontroller_master', 'domaincontroller_backup','domaincontroller_slave','memberserver','basesystem','managed_client','mobile_client'] }

	def depends(self):
		return {}

 	def mapping(self,value):
		if value in ['normal','Normal']:
			return 'normal'
		elif value in ['strict','Strict']:
			return 'strict'
		elif value in ['open','Open']:
			return 'open'

	def profile_complete(self):
		if self.check('security_profile'):
			return False
		return True

	def layout(self):
		self.reset_layout()
		self.add_elem('security_profile_label0', textline(_('Activate filtering of system services:'), self.minY+1, self.minX+2))
		self.add_elem('security_profile_label1', textline(_('These options control how many system services are'), self.minY+2, self.minX+2))
		self.add_elem('security_profile_label2', textline(_('initially blocked by a packet filter (iptables)'), self.minY+3, self.minX+2))

#		self.add_elem('security_profile_label3', textline(_('    allowed. Unsuitable for a typical production setup.'), self.minY+8, self.minX+2))
		self.add_elem('security_profile_label3', textline(_('    allowed.'), self.minY+8, self.minX+2))

		dict={}
		dict[_('Disabled')]=['open',0]
		dict[_('Typical selection of services, recommended')]=['normal',1]
		dict[_('Locked-down setup. Only SSH, LDAP and HTTPS are')]=['strict',2]

		list=['normal','strict','open']
		select=1

		if self.all_results.has_key('security/profile'):
			if self.all_results['security/profile'] == "open":
				select = 0
			elif self.all_results['security/profile'] == "strict":
				select = 2
		
		self.add_elem('security_profile_radio', radiobutton(dict,self.minY+5,self.minX+2,50,10,[select]))
		self.get_elem('security_profile_radio').current = select

		self.add_elem('BT_back', button(_('F11-Back'),self.minY+18,self.minX+2))
		self.add_elem('BT_next', button(_('F12-Next'),self.minY+18,self.minX+16+(self.width)-37))

		self.current = self.get_elem_id('security_profile_radio')
		self.get_elem_by_id(self.current).set_on()

	def input(self,key):

		if key in [ 10, 32 ] and self.get_elem('BT_back').get_status():
			return 'prev'

		elif key in [ 10, 32 ] and self.get_elem('BT_next').get_status():
			return 'next'

		else:
			try:
				return self.get_elem_by_id(self.current).key_event(key)
			except:
				pass

	def incomplete(self):
		return 0

	def helptext(self):
		return _('Security Settings  \n \n Pre-defined packet filter configuration options for various system roles')

	def modheader(self):
		return _('Security Settings')

	def result(self):
		result={}

		if self.get_elem('security_profile_radio').result() == 'open':
			result['security_profile'] = 'open'
		elif self.get_elem('security_profile_radio').result() == 'normal':
			result['security_profile'] = 'normal'
		elif self.get_elem('security_profile_radio').result() == 'strict':
			result['security_profile'] = 'strict'

		return result
