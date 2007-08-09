# -*- coding: utf-8 -*-
#
# Univention Admin Modules
#  admin policy for the registry configuration
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

import sys, string
import univention.admin.syntax
import univention.admin.filter
import univention.admin.handlers
import univention.admin.localization
import univention.debug

translation=univention.admin.localization.translation('univention.admin.handlers.policies')
_=translation.translate

class xfreeFixedAttributes(univention.admin.syntax.select):
	name='registryFixedAttributes'
	choices=[
		('univentionXVideoRam',_('Description')),
		]

module='policies/registry'
operations=['add','edit','remove','search']

policy_oc='univentionPolicyRegistryConfiguration'
policy_apply_to=[]
policy_position_dn_prefix="cn=registry"
usewizard=1
childs=0
short_description=_('Policy: Config Registry')
policy_short_description=_('Config Registry Settings')
long_description=''
options={
}
property_descriptions={
	'name': univention.admin.property(
			short_description=_('Name'),
			long_description='',
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=1,
			may_change=0,
			identifies=1,
		),
	'registry': univention.admin.property(
			short_description=_('Config Registry'),
			long_description='',
			syntax=univention.admin.syntax.string,
			multivalue=1,
			options=[],
			required=0,
			may_change=1,
			identifies=0,
		),
	'requiredObjectClasses': univention.admin.property(
			short_description=_('Required Object Classes'),
			long_description='',
			syntax=univention.admin.syntax.string,
			multivalue=1,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'prohibitedObjectClasses': univention.admin.property(
			short_description=_('Prohibited Object Classes'),
			long_description='',
			syntax=univention.admin.syntax.string,
			multivalue=1,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'fixedAttributes': univention.admin.property(
			short_description=_('Fixed Attributes'),
			long_description='',
			syntax=xfreeFixedAttributes,
			multivalue=1,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'emptyAttributes': univention.admin.property(
			short_description=_('Empty Attributes'),
			long_description='',
			syntax=xfreeFixedAttributes,
			multivalue=1,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'filler': univention.admin.property(
			short_description='',
			long_description='',
			syntax=univention.admin.syntax.none,
			multivalue=0,
			required=0,
			may_change=1,
			identifies=0,
			dontsearch=1
		)
}
layout=[
	univention.admin.tab(_('General'),_('Display Settings'), [
		[univention.admin.field('name', hide_in_resultmode=1), univention.admin.field('filler', hide_in_normalmode=1) ],
		[univention.admin.field('registry'), univention.admin.field('filler')],
	]),
	univention.admin.tab(_('Object'),_('Object'), [
		[univention.admin.field('requiredObjectClasses') , univention.admin.field('prohibitedObjectClasses') ],
		[univention.admin.field('fixedAttributes'), univention.admin.field('emptyAttributes')]
	]),
]

mapping=univention.admin.mapping.mapping()
mapping.register('name', 'cn', None, univention.admin.mapping.ListToString)
mapping.register('requiredObjectClasses', 'requiredObjectClasses')
mapping.register('prohibitedObjectClasses', 'prohibitedObjectClasses')
mapping.register('fixedAttributes', 'fixedAttributes')
mapping.register('emptyAttributes', 'emptyAttributes')

class object(univention.admin.handlers.simplePolicy):
	module=module

	def __init__(self, co, lo, position, dn='', superordinate=None, arg=None):
		global mapping
		global property_descriptions

		self.co=co
		self.lo=lo
		self.dn=dn
		self.position=position
		self._exists=0
		self.mapping=mapping
		self.descriptions=property_descriptions

		univention.admin.handlers.simplePolicy.__init__(self, co, lo, position, dn, superordinate)

	def open(self):
		univention.admin.handlers.simplePolicy.open(self)
		if self.dn:
			self['registry']=[]
			for key in self.oldattr.keys():
				if key.startswith('univentionRegistry;entry-'):
					self['registry'].append('%s=%s' % (key.split('univentionRegistry;entry-')[1].replace('-','/'), self.oldattr[key][0]))

		self.save()

	def _ldap_modlist(self):
		ml=univention.admin.handlers.simplePolicy._ldap_modlist(self)
		if self.hasChanged('registry'):
			old_keys = []
			new_keys = []
			if self.info.has_key('registry'):
				for line in self.info['registry']:
					new_keys.append(line.split('=')[0])
			if self.oldinfo.has_key('registry'):
				for line in self.oldinfo['registry']:
					old_keys.append(line.split('=')[0])
			for k in old_keys:
				if not k in new_keys:
					ml.append( ('univentionRegistry;entry-%s' % k.replace('/','-'), self.oldattr.get('univentionRegistry;entry-%s' % k, ''), ''))
			for k in new_keys:
				if not k in old_keys:
					for line in self.info['registry']:
						if line.startswith('%s=' % k ):
							ml.append( ('univentionRegistry;entry-%s' % k.replace('/','-'), '', '%s' % string.join(line.split('=')[1:])) )
							break
		return ml


	def exists(self):
		return self._exists

	def _ldap_pre_create(self):
		self.dn='%s=%s,%s' % (mapping.mapName('name'), mapping.mapValue('name', self.info['name']), self.position.getDn())

	def _ldap_addlist(self):
		return [
			('objectClass', ['top', 'univentionPolicy', 'univentionPolicyRegistry'])
		]

def lookup(co, lo, filter_s, base='', superordinate=None, scope='sub', unique=0, required=0, timeout=-1, sizelimit=0):

	filter=univention.admin.filter.conjunction('&', [
		univention.admin.filter.expression('objectClass', 'univentionPolicyRegistry'),
		])

	if filter_s:
		filter_p=univention.admin.filter.parse(filter_s)
		univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
		filter.expressions.append(filter_p)

	res=[]
	try:
		for dn in lo.searchDn(unicode(filter), base, scope, unique, required, timeout, sizelimit):
			res.append(object(co, lo, None, dn))
	except:
		pass
	return res

def identify(dn, attr, canonical=0):

	return 'univentionPolicyXConfiguration' in attr.get('objectClass', [])
