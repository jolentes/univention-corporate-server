#!/usr/bin/python2.4
# -*- coding: utf-8 -*-
#
# Univention Management Console
#  module: management of virtualization servers
#
# Copyright 2010 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

import univention.management.console as umc
import univention.management.console.handlers as umch
import univention.management.console.dialog as umcd
import univention.management.console.tools as umct
import univention.management.console.protocol as umcp

import univention.debug as ud
import univention.config_registry as ucr
import univention.service_info as usi
import univention.uvmm.node as uuv_node
import univention.uvmm.protocol as uuv_proto

import copy
import operator
import os
import socket
import time

import notifier.popen

import uvmmd
from treeview import TreeView
from tools import *
from types import *
from wizards import *

configRegistry = ucr.ConfigRegistry()
configRegistry.load()

_ = umc.Translation('univention.management.console.handlers.uvmm').translate
_uvmm_locale = umc.Translation('univention.virtual.machine.manager').translate

name = 'uvmm'
icon = 'uvmm/module'
short_description = _('Virtual Machines (UVMM)')
long_description = _('Univention Virtual Machine Manager')
categories = [ 'system', 'all' ]
hide_tabs = True

# fields of a drive definition
drive_type = umcd.make( ( 'type', DriveTypeSelect( _( 'Type' ) ) ), attributes = { 'width' : '250' } )
drive_uri = umcd.make( ( 'uri', umc.String( 'URI' ) ), attributes = { 'width' : '250' } )
drive_dev = umcd.make( ( 'dev', umc.String( _( 'Drive' ) ) ), attributes = { 'width' : '250' } )

boot_dev = umcd.make( ( 'bootdev', BootDeviceSelect( _( 'Boot order' ) ) ), attributes = { 'width' : '200' } )

dest_node_select = NodeSelect( _( 'Destination host' ) )
arch_select = ArchSelect( _( 'Architecture' ) )
type_select = VirtTechSelect( _( 'Virtualization Technology' ), may_change = False )
cpus_select = NumberSelect( _( 'Number of CPUs' ) )

command_description = {
	'uvmm/overview': umch.command(
		short_description = _('Overview'),
		long_description = _('Overview'),
		method = 'uvmm_overview',
		values = {},
		startup = True,
		),
	'uvmm/group/overview': umch.command(
		short_description = _('Show group information'),
		long_description = _('Show group information'),
		method = 'uvmm_group_overview',
		values = { 'group' : umc.String( 'group' ) },
		),
	'uvmm/node/overview': umch.command(
		short_description = _('Show physical server information'),
		long_description = _('Show physical server information'),
		method = 'uvmm_node_overview',
		values = { 'node' : umc.String( 'node' ) },
		),
	'uvmm/domain/overview': umch.command(
		short_description = _('Show instance information'),
		long_description = _('Show instance information'),
		method = 'uvmm_domain_overview',
		values = { 'domain' : umc.String( 'domain' ) },
		),
	'uvmm/domain/create': umch.command(
		short_description = _('Create a virtual instance'),
		long_description = _('Create a virtual instance'),
		method = 'uvmm_domain_create',
		values = { 'group' : umc.String( 'group' ),
				   'node' : umc.String( 'node' ) },
		),
	'uvmm/domain/remove/images': umch.command(
		short_description = _('Remove drives of a virtual instance'),
		long_description = _('Remove drives of a virtual instance'),
		method = 'uvmm_domain_remove_images',
		values = { 'group' : umc.String( 'group' ),
				   'node' : umc.String( 'node' ),
				   'domain' : umc.String( 'domain' ),
				   },
		),
	'uvmm/domain/remove': umch.command(
		short_description = _('Remove a virtual instance'),
		long_description = _('Remove a virtual instance'),
		method = 'uvmm_domain_remove',
		values = { 'group' : umc.String( 'group' ),
				   'node' : umc.String( 'node' ),
				   'domain' : umc.String( 'domain' ),
				   'drives' : umc.StringList( '' ),
				   },
		confirm = umch.Confirm( _( 'Remove virtual instance' ), _( 'Are you sure that the virtual instance should be removed?' ) ),
		),
	'uvmm/domain/configure': umch.command(
		short_description = _('Configuration of virtual instances'),
		long_description = _('Configuration of virtual instances'),
		method = 'uvmm_domain_configure',
		values = { 'domain' : umc.String( 'instance' ), # last name, which was used to load the configuration
				   'name' : umc.String( _( 'Name' ) ), # new name
				   'mac' : umc.String( _( 'MAC address' ), required = False ),
				   'memory' : umc.String( _( 'Memory' ) ),
				   'interface' : umc.String( _( 'Interface' ) ),
				   'cpus' : cpus_select,
				   'vnc' : umc.Boolean( _( 'VNC remote access' ) ),
				   'vnc_global' : umc.Boolean( _( 'Available globally' ) ),
				   'vnc_passwd' : umc.Password( _( 'Password' ), required = False ),
				   'kblayout' : KBLayoutSelect( _( 'Keyboard layout' ) ),
				   'arch' : arch_select,
				   'type' : type_select,
				   'drives' : umc.StringList( _( 'Drive' ) ),
				   'os' : umc.String( _( 'Operating System' ), required = False ),
				   'user' : umc.String( _( 'User' ), required = False ),
				   'advkernelconf' : umc.Boolean( _( 'Advanved kernel configuration' ), required = False ),
				   'initrd' : umc.String( _( 'RAM disk' ), required = False ),
				   'cmdline' : umc.String( _( 'Kernel parameter' ), required = False ),
				   'kernel' : umc.String( _( 'Kernel' ), required = False ),
				   'bootdevs' : umc.StringList( _( 'Boot order' ), required = False ),
				   },
		),
	'uvmm/domain/migrate': umch.command(
		short_description = _( 'Migration of virtual instances' ),
		long_description = _( 'Migration of virtual instances' ),
		method = 'uvmm_domain_migrate',
		values = { 'domain' : umc.String( _( 'domain' ) ),
				   'source' : umc.String( 'source node' ),
				   'dest' : dest_node_select,
				  },
		),
	'uvmm/domain/snapshot/create': umch.command(
		short_description=_('Save virtual instance'),
		long_description=_('Saves the state of a virtual instance'),
		method='uvmm_domain_snapshot_create',
		values={
			'node': umc.String('node'),
			'domain': umc.String('domain'),
			'snapshot': umc.String(_('snapshot name')),
			},
		),
	'uvmm/domain/snapshot/revert': umch.command(
		short_description=_('Restore virtual instance'),
		long_description=_('Restore the state of a virtual instance'),
		method='uvmm_domain_snapshot_revert',
		confirm=umch.Confirm(_('Revert to snapshot'), _('Are you sure that the instance should be reverted to this snapshot?')),
		values={
			'node': umc.String('node'),
			'domain': umc.String('domain'),
			'snapshot': umc.String(_('snapshot name')),
			},
		),
	'uvmm/domain/snapshot/delete': umch.command(
		short_description=_('Delete snapshot'),
		long_description=_('Delete the state of a virtual instance'),
		method='uvmm_domain_snapshot_delete',
		confirm=umch.Confirm(_('Remove snapshot'), _('Are you sure that the snapshot should be removed?')),
		values={
			'node': umc.String('node'),
			'domain': umc.String('domain'),
			'snapshot': umc.String(_('snapshot name')),
			},
		),
	'uvmm/domain/state': umch.command(
		short_description = _( 'Change state of a virtual instance' ),
		long_description = _('Change state of virtual instances' ),
		method = 'uvmm_domain_state',
		values = { 'node' : umc.String( _( 'Instance' ) ),
				   'domain' : umc.String( 'Physical server' ),
				   'state' : umc.String( 'State' ),
				  },
		),
	'uvmm/domain/stop': umch.command(
		short_description = _( 'Stop a virtual instance' ),
		long_description = _('Stop a virtual instance' ),
		method = 'uvmm_domain_state',
		confirm = umch.Confirm( _( 'Stop' ), _( 'Stopping the virtual instance will turn it off without shutting down the operating system. Should the virtual instance be stopped?' ) ),
		values = { 'node' : umc.String( _( 'Instance' ) ),
				   'domain' : umc.String( 'Physical server' ),
				   'state' : umc.String( 'State' ),
				  },
		),
	'uvmm/drive/create': umch.command(
		short_description = _( 'New Drive' ),
		long_description = _('Create a new drive' ),
		method = 'uvmm_drive_create',
		values = {},
		),
	'uvmm/drive/remove': umch.command(
		short_description = _( 'Remove Drive' ),
		long_description = _('Removes a drive' ),
		method = 'uvmm_drive_remove',
		values = {},
		),
	'uvmm/drive/bootdevice': umch.command(
		short_description = _( 'Set drive as boot device' ),
		long_description = _('Set drive as boot device' ),
		method = 'uvmm_drive_bootdevice',
		values = {},
		),
	'uvmm/daemon/restart': umch.command(
		short_description = _( 'Restarts libvirt service' ),
		long_description = _( 'Restarts libvirt service' ),
		method = 'uvmm_daemon_restart',
		values = {},
		),
}

class handler( umch.simpleHandler ):
	# level 0 is the container list
	STATES = {
		0 : _( 'unknown' ),
		1 : _( 'running' ),
		2 : _( 'idle' ),
		3 : _( 'paused' ),
		4 : _( 'shut down' ),
		5 : _( 'shut off' ),
		6 : _( 'crashed' ),
		}

	def __init__( self ):
		global command_description
		umch.simpleHandler.__init__( self, command_description )
		self.uvmm = uvmmd.Client( auto_connect = False )
		self.drive_wizard = DriveWizard( 'uvmm/drive/create' )
		self.domain_wizard = InstanceWizard( 'uvmm/domain/create' )

	@staticmethod
	def _getattr( object, attr, default = '' ):
		value = getattr( object, attr, default )
		if value == None:
			value = ''
		return str( value )

	@staticmethod
	def _getstr( object, attr, default = '' ):
		value = object.options.get( attr, default )
		if value == None:
			value = default
		return value

	def set_content( self, object, content ):
		# create position links
		lst = umcd.List( attributes = { 'width' : '100%', 'type' : 'umc_mini_padding umc_nowrap' } )
		row = []
		options = {}
		keys = []
		refresh = ''
		slash = umcd.Cell( umcd.HTML( '&rarr;' ), attributes = { 'type' : 'umc_mini_padding umc_nowrap' } )
		row.append( umcd.Cell( umcd.HTML( '<b>%s</b>' % _( 'Location:' ) ), attributes = { 'type' : 'umc_mini_padding umc_nowrap' } ) )
		if 'group' in object.options:
			keys.append( 'group' )
			if 'node' in object.options or 'source' in object.options or 'dest' in object.options:
				if 'node' in object.options:
					key = 'node'
				else:
					key = 'dest'
					if 'source' in object.options:
						key = 'source'
				options[ 'node' ] = object.options[ key ]
				keys.append( 'node' )
				if 'domain' in object.options and object.options[ 'domain' ] != 'NONE':
					keys.append( 'domain' )
		opts = {}
		for key in keys[ : -1 ]:
			opts[ key ] = object.options[ key ]
			cmd = umcp.SimpleCommand( 'uvmm/%s/overview' % key , options = copy.copy( opts ) )
			# FIXME: should be removed if UVMMd supports groups
			if key == 'group' and object.options[ key ] == 'default':
				text = _( 'Physical servers' )
			elif key in ( 'node', 'dest', 'source' ):
				text = object.options[ key ]
				if '.' in text:
					text = text[ : text.find( '.' ) ]
			else:
				text = object.options[ key ]
			lnk = umcd.LinkButton( text , actions = [ umcd.Action( cmd ) ] )
			row.append( umcd.Cell( lnk, attributes = { 'type' : 'umc_mini_padding umc_nowrap' } ) )
			row.append( slash )
		refresh = keys[ -1 ]
		opts[ keys[ -1 ] ] = object.options[ keys[ -1 ] ]
		# FIXME: should be removed if UVMMd supports groups
		if refresh == 'group' and opts[ refresh ] == 'default':
			text = _( 'Physical servers' )
		else:
			text = object.options[ refresh ]
		if refresh in ( 'node', 'dest', 'source' ):
			if '.' in text:
				text = text[ : text.find( '.' ) ]
		row.append( umcd.Cell( umcd.Text( text ), attributes = { 'type' : 'umc_mini_padding umc_nowrap' } ) )

		reload_cmd = umcp.SimpleCommand( 'uvmm/%s/overview' % refresh, options = copy.copy( opts ) )
		reload_btn = umcd.LinkButton( _( 'Refresh' ), 'actions/refresh', actions = [ umcd.Action( reload_cmd ) ] )
		reload_btn.set_size( umct.SIZE_SMALL )
		row.append( umcd.Cell( reload_btn, attributes = { 'width' : '100%', 'align' : 'right', 'type' : 'umc_mini_padding' } ) )
		lst.add_row( row, attributes = { 'type' : 'umc_mini_padding' } )
		object.dialog[ 0 ].set_dialog( umcd.List( content = [ [ lst, ], [ content, ] ] ) )

	def uvmm_overview( self, object ):
		"""Toplevel overview: show info."""
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object )
		if success:
			self.domain_wizard.reset()
			res.dialog[ 0 ].set_dialog( umcd.ModuleDescription( 'Univention Virtual Machine Manager (UVMM)', _( 'This module provides a management interface for physical servers that are registered within the UCS domain.\nThe tree view on the left side shows an overview of all existing physical servers and the residing virtual instances. By selecting one of the physical servers statistics of the current state are displayed to get an impression of the health of the hardware system. Additionally actions like start, stop, suspend and resume for each virtual instance can be invoked on each of the instances.\nAlso possible is the remote access to virtual instances via VNC. Therefor it must be activated in the configuration.\nEach virtual instance entry in the tree view provides access to detailed information und gives the possibility to change the configuration or state and migrated it to another physical server.' ) ) )
		self.finished( object.id(), res )

	def uvmm_group_overview( self, object ):
		"""Group overview: show nodes of group with utilization."""
		ud.debug( ud.ADMIN, ud.INFO, 'Group overview' )
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', ) )
		if not success:
			self.finished(object.id(), res)
			return
		self.domain_wizard.reset()
		nodes = self.uvmm.get_group_info( object.options[ 'group' ] )

		table = umcd.List()
		table.set_header( [ _( 'Physical server' ), _( 'CPU usage' ), _( 'Memory usage' ) ] )
		for node_info in sorted(nodes, key=operator.attrgetter('name')):
			node_cmd = umcp.SimpleCommand( 'uvmm/node/overview', options = { 'group' : object.options[ 'group' ], 'node' : node_info.name } )
			node_btn = umcd.LinkButton( node_info.name, actions = [ umcd.Action( node_cmd ) ] )
			node_uri = self.uvmm.node_name2uri( node_info.name )
			if node_uri.startswith( 'xen' ):
				cpu_usage = percentage(float(node_info.cpu_usage) / 10.0, width=150)
			else:
				cpu_usage = umcd.HTML( '<i>%s</i>' % _( 'not available' ) )
			mem_usage = percentage( float( node_info.curMem ) / node_info.phyMem * 100, '%s / %s' % ( MemorySize.num2str( node_info.curMem ), MemorySize.num2str( node_info.phyMem ) ), width = 150 )
			table.add_row( [ node_btn, cpu_usage, mem_usage ] )
		self.set_content( res, table )
		self.finished(object.id(), res)

	def _create_domain_buttons( self, object, node_info, domain_info, overview = 'node', operations = False, remove_failure = 'domain' ):
		"""Create buttons to manage domain."""
		buttons = []
		overview_cmd = umcp.SimpleCommand( 'uvmm/%s/overview' % overview, options = object.options )
		comma = umcd.HTML( '&nbsp;' )
		# migrate? if parameter set and state is not paused
		if configRegistry.is_true('uvmm/umc/show/migrate', True) and operations and domain_info.state != 3:
			cmd = umcp.SimpleCommand( 'uvmm/domain/migrate', options = { 'group' : object.options[ 'group' ], 'source' : node_info.name, 'domain' : domain_info.name } )
			buttons.append( umcd.LinkButton( _( 'Migrate' ), actions = [ umcd.Action( cmd ) ] ) )
			buttons.append( comma )

		# Start? if state is not running, blocked or paused
		cmd_opts = { 'group' : object.options[ 'group' ], 'node' : node_info.name, 'domain' : domain_info.name }
		if not domain_info.state in ( 1, 2, 3 ):
			opts = copy.copy( cmd_opts )
			opts[ 'state' ] = 'RUN'
			cmd = umcp.SimpleCommand( 'uvmm/domain/state', options = opts )
			buttons.append( umcd.LinkButton( _( 'Start' ), actions = [ umcd.Action( cmd ), umcd.Action( overview_cmd ) ] ) )
			buttons.append( comma )

		# Stop? if state is not stopped
		if not domain_info.state in ( 4, 5 ):
			opts = copy.copy( cmd_opts )
			opts[ 'state' ] = 'SHUTDOWN'
			cmd = umcp.SimpleCommand( 'uvmm/domain/stop', options = opts )
			buttons.append( umcd.LinkButton( _( 'Stop' ), actions = [ umcd.Action( cmd ), umcd.Action( overview_cmd ) ] ) )
			buttons.append( comma )

		# Pause? if state is running or idle
		if configRegistry.is_true('uvmm/umc/show/pause', True) and domain_info.state in ( 1, 2):
			opts = copy.copy( cmd_opts )
			opts[ 'state' ] = 'PAUSE'
			cmd = umcp.SimpleCommand( 'uvmm/domain/state', options = opts )
			buttons.append( umcd.LinkButton( _( 'Pause' ), actions = [ umcd.Action( cmd ), umcd.Action( overview_cmd ) ] ) )
			buttons.append( comma )

		# Suspend? if state is running or idle
		if configRegistry.is_true('uvmm/umc/show/suspend', True) and hasattr(node_info, 'supports_suspend') and node_info.supports_suspend and domain_info.state in (1, 2):
			opts = copy.copy(cmd_opts)
			opts['state'] = 'SUSPEND'
			cmd = umcp.SimpleCommand( 'uvmm/domain/state', options = opts )
			buttons.append(umcd.LinkButton(_('Suspend'), actions = [umcd.Action(cmd), umcd.Action(overview_cmd)]))
			buttons.append(comma)

		# Resume? if state is paused
		if configRegistry.is_true('uvmm/umc/show/pause', True) and domain_info.state in ( 3, ):
			opts = copy.copy( cmd_opts )
			opts[ 'state' ] = 'RUN'
			cmd = umcp.SimpleCommand( 'uvmm/domain/state', options = opts )
			buttons.append( umcd.LinkButton( _( 'Unpause' ), actions = [ umcd.Action( cmd ), umcd.Action( overview_cmd ) ] ) )
			buttons.append( comma )

		# Remove? always
		if operations:
			opts = copy.copy( cmd_opts )
			cmd = umcp.SimpleCommand( 'uvmm/domain/remove/images', options = opts )
			buttons.append( umcd.LinkButton( _( 'Remove' ), actions = [ umcd.Action( cmd ), ] ) )
			buttons.append( comma )

		# create drive
		# if operations:
		# 	opts = copy.copy( cmd_opts )
		# 	cmd = umcp.SimpleCommand( 'uvmm/drive/create', options = opts )
		# 	buttons.append( umcd.LinkButton( _( 'New Drive' ), actions = [ umcd.Action( cmd ), ] ) )
		# 	buttons.append( comma )

		# VNC? if running and activated
		if configRegistry.is_true('uvmm/umc/show/vnc', True) and domain_info.state in ( 1, 2 ) and domain_info.graphics and domain_info.graphics[ 0 ].port != -1:
			vnc = domain_info.graphics[0]
			host = node_info.name
			try:
				VNC_LINK_BY_NAME, VNC_LINK_BY_IPV4, VNC_LINK_BY_IPV6 = range(3)
				vnc_link_format = VNC_LINK_BY_IPV4
				if vnc_link_format == VNC_LINK_BY_IPV4:
					addrs = socket.getaddrinfo(host, vnc.port, socket.AF_INET)
					(family, socktype, proto, canonname, sockaddr) = addrs[0]
					host = sockaddr[0]
				elif vnc_link_format == VNC_LINK_BY_IPV6:
					addrs = socket.getaddrinfo(host, vnc.port, socket.AF_INET6)
					(family, socktype, proto, canonname, sockaddr) = addrs[0]
					host = '[%s]' % sockaddr[0]
			except: pass
			helptext = '%s:%s' % (host, vnc.port)
			if configRegistry.get('uvmm/umc/vnc', 'internal').lower() in ('external', ):
				uri = 'vnc://%s:%s' % (host, vnc.port)
				html = umcd.HTML('<a class="nounderline" target="_blank" href="%s" title="%s"><span class="content">VNC</span></a>' % (uri, helptext))
			else:
				popupwindow = ("<html><head><title>" + \
				               _("%(dn)s on %(nn)s") + \
				               "</title></head><body>" + \
				               "<applet archive='/TightVncViewer.jar' code='com.tightvnc.vncviewer.VncViewer' height='100%%' width='100%%'>" + \
				               "<param name='host' value='%(h)s' />" + \
				               "<param name='port' value='%(p)s' />" + \
				               "<param name='offer relogin' value='no' />" + \
				               "</applet>" + \
				               "</body></html>") % {'h': host, 'p': vnc.port, 'nn': node_info.name, 'dn': domain_info.name}
				id = ''.join([c for c in '%s%s' % (host, vnc.port) if c.lower() in set('abcdefghijklmnopqrstuvwxyz0123456789') ])
				javascript = "var w=window.open('','VNC%s','dependent=no,resizable=yes');if(w.document.applets.length > 0){w.focus();}else{w.document.write('%s');w.document.close();};return false;" % (id, popupwindow.replace("'", "\\'"))
				html = umcd.HTML('<a class="nounderline" href="#" onClick="%s" title="%s"><span class="content">VNC</span></a>' % (javascript, helptext))
			buttons.append( html )
			buttons.append( comma )

		# Snapshot? always
		if operations and configRegistry.is_true('uvmm/umc/show/snapshot', True) and hasattr(domain_info, 'snapshots') and isinstance(domain_info.snapshots, dict):
			opts = copy.copy(cmd_opts)
			create_cmd = umcp.SimpleCommand('uvmm/domain/snapshot/create', options=opts)
			create_cmd.incomplete = True
			create_act = [umcd.Action(create_cmd),]
			choices = [
					{'description': '---', 'actions': '::none'},
					{'description': _('Create new snapshot'), 'actions': create_act},
					]
			revert_choices = []
			delete_choices = []
			f = lambda s: s[1].ctime
			for snapshot_name, snap in sorted(domain_info.snapshots.items(), key=f, reverse=True):
				ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(snap.ctime))
				name = '%s (%s)' % (snapshot_name, ctime)
				opts = copy.copy(cmd_opts)
				opts['snapshot'] = snapshot_name

				revert_cmd = umcp.SimpleCommand('uvmm/domain/snapshot/revert', options=opts)
				revert_act = [umcd.Action(revert_cmd), umcd.Action(overview_cmd)]
				revert_choices.append({'description': _('Revert to %s') % name, 'actions': revert_act})

				delete_cmd = umcp.SimpleCommand('uvmm/domain/snapshot/delete', options=opts)
				delete_act = [umcd.Action(delete_cmd), umcd.Action(overview_cmd)]
				delete_choices.append({'description': _('Remove %s') % name, 'actions': delete_act})
			if revert_choices:
				#choices.append({'description': '---', 'actions': '::none'}) # FIXME: dnw
				choices.extend(revert_choices)
			if delete_choices:
				#choices.append({'description': '---', 'actions': '::none'}) # FIXME: dnw
				choices.extend(delete_choices)
			buttons.append(umcd.ChoiceButton(_('Snapshots'), choices))
			buttons.append(comma)

		return buttons[ : -1 ]

	def _drive_name( self, drive ):
		"""Translate disk type to display-string."""
		if drive == uvmmn.Disk.DEVICE_DISK:
			return _( 'hard drive' )
		else:
			return _( 'CDROM drive' )

	def uvmm_node_overview( self, object ):
		"""Node overview: show node utilization and all domains."""
		ud.debug( ud.ADMIN, ud.INFO, 'Node overview' )
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'node' ) )
		if not success:
			self.finished(object.id(), res)
			return
		self.domain_wizard.reset()

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		if not node_uri:
			res.dialog[ 0 ].set_dialog( umcd.InfoBox( _( 'The physical server is not available at the moment' ) ) )
			self.finished(object.id(), res)
			return
		node_info = self.uvmm.get_node_info( node_uri )

		content = umcd.List( attributes = { 'width' : '100%' } )

		node_table = umcd.List( attributes = { 'width' : '100%' } )
		# node_cmd = umcp.SimpleCommand( 'uvmm/node/overview', options = { 'group' : object.options[ 'group' ], 'node' : node_info.name } )
		# node_btn = umcd.LinkButton( node.name, actions = [ umcd.Action( node_cmd ) ] )
		if node_uri.startswith( 'xen' ):
			cpu_usage = percentage(float(node_info.cpu_usage) / 10.0, width=150)
		else:
			cpu_usage = umcd.HTML( '<i>%s</i>' % _( 'CPU usage not available' ) )
		mem_usage = percentage( float( node_info.curMem ) / node_info.phyMem * 100, '%s / %s' % ( MemorySize.num2str( node_info.curMem ), MemorySize.num2str( node_info.phyMem ) ), width = 150 )
		# node_table.add_row( [ _( 'Physical server' ), node_btn ] )
		node_table.add_row( [ _( 'CPU usage' ), umcd.Cell( cpu_usage, attributes = { 'width' : '100%' } ) ] )
		node_table.add_row( [ _( 'Memory usage' ), umcd.Cell( mem_usage, attributes = { 'width' : '100%' } ) ] )
		content.add_row( [ umcd.Section( _( 'Physical server' ), node_table, attributes = { 'width' : '100%' } ) ] )

		table = umcd.List( attributes = { 'type' : 'umc_mini_padding' } )
		num_buttons = 0
		for domain_info in sorted( node_info.domains, key = operator.attrgetter( 'name' ) ):
			# ignore XEN Domain-0
			if domain_info.name == 'Domain-0':
				continue
			domain_cmd = umcp.SimpleCommand( 'uvmm/domain/overview', options = { 'group' : object.options[ 'group' ], 'node' : node_info.name, 'domain' : domain_info.name } )
			domain_icon = 'uvmm/domain'
			if domain_info.state in ( 1, 2 ):
				domain_icon = 'uvmm/domain-on'
			elif domain_info.state in ( 3, ):
				domain_icon = 'uvmm/domain-paused'
			domain_btn = umcd.LinkButton( domain_info.name, tag = domain_icon, actions = [ umcd.Action( domain_cmd ) ] )
			domain_btn.set_size( umct.SIZE_SMALL )
			buttons = self._create_domain_buttons( object, node_info, domain_info, remove_failure = 'node' )
			if len( buttons ) > num_buttons:
				num_buttons = len( buttons )
			# os = getattr( domain_info, 'annotations', {} ).get( 'os', '' )
			# if len( os ) > 15:
			# 	os = os[ : 13 ] + '...'
			table.add_row( [ umcd.Cell( domain_btn, attributes = { 'type' : 'umc_mini_padding' } ), umcd.Cell( percentage( float( domain_info.cputime[ 0 ] ) / 10, width = 80 ), attributes = { 'type' : 'umc_mini_padding' } ), umcd.Cell( umcd.Number( MemorySize.num2str( domain_info.maxMem ) ), attributes = { 'type' : 'umc_mini_padding' } ), umcd.Cell( buttons, attributes = { 'type' : 'umc_mini_padding umc_nowrap' } ) ], attributes = { 'type' : 'umc_mini_padding' } )# + buttons )

		if len( table.get_content() ):
			table.set_header( [ _( 'Instance' ), _( 'CPU usage' ), _( 'Memory' ) ] )

		content.add_row( [ umcd.Cell( table, attributes = { 'colspan' : '2' } ), ] )
		self.set_content( res, content )
		self.finished(object.id(), res)

	def _dlg_domain_settings( self, object, node_info, domain_info ):
		"""Create domain setting widgets."""
		domain_is_off = 5 == domain_info.state
		content = umcd.List()

		types = []
		archs = []
		for template in node_info.capabilities:
			tech = '%s-%s' % ( template.domain_type, template.os_type )
			ud.debug( ud.ADMIN, ud.INFO, 'domain settings: virtualisation technology: %s' % tech )
			if not tech in VirtTechSelect.MAPPING:
				continue
			if not tech in types:
				types.append( tech )
			if not template.arch in archs:
				archs.append( template.arch )
		type_select.update_choices( types )
		arch_select.update_choices( archs )

		# if domain is not stopped ...
		make_func = domain_is_off and umcd.make or umcd.make_readonly
		name = make_func( self[ 'uvmm/domain/configure' ][ 'name' ], default = handler._getattr( domain_info, 'name', '' ), attributes = { 'width' : '250' } )
		tech_default = '%s-%s' % ( handler._getattr( domain_info, 'domain_type', 'xen' ), handler._getattr( domain_info, 'os_type', 'hvm' ) )
		virt_tech = umcd.make_readonly( self[ 'uvmm/domain/configure' ][ 'type' ], default = tech_default, attributes = { 'width' : '250' } )
		arch = make_func( self[ 'uvmm/domain/configure' ][ 'arch' ], default = handler._getattr( domain_info, 'arch', 'i686' ), attributes = { 'width' : '250' } )
		os_widget = make_func( self[ 'uvmm/domain/configure' ][ 'os' ], default = getattr(domain_info, 'annotations', {}).get('os', ''), attributes = { 'width' : '250' } )
		cpus_select.max = int( node_info.cpus )
		cpus = make_func( self[ 'uvmm/domain/configure' ][ 'cpus' ], default = handler._getattr( domain_info, 'vcpus', '1' ), attributes = { 'width' : '250' } )
		mem = handler._getattr(domain_info, 'maxMem', str(512<<10)) # KiB
		memory = make_func( self[ 'uvmm/domain/configure' ][ 'memory' ], default = MemorySize.num2str( mem ), attributes = { 'width' : '250' } )
		if domain_info and domain_info.interfaces:
			iface = domain_info.interfaces[ 0 ]
			iface_mac = iface.mac_address
			iface_source = iface.source
		else:
			iface_mac = ''
			iface_source = 'eth0'
		mac = make_func( self[ 'uvmm/domain/configure' ][ 'mac' ], default = iface_mac, attributes = { 'width' : '250' } )
		interface = make_func( self[ 'uvmm/domain/configure' ][ 'interface' ], default = iface_source, attributes = { 'width' : '250' } )
		# if no bootloader is set we use the advanced kernel configuration options
		if handler._getattr( domain_info, 'bootloader', '' ):
			akc = False
		else:
			akc = True
		advkernelconf = make_func( self[ 'uvmm/domain/configure' ][ 'advkernelconf' ], default = akc )
		ram_disk = make_func( self[ 'uvmm/domain/configure' ][ 'initrd' ], default = handler._getattr( domain_info, 'initrd', '' ), attributes = { 'width' : '250' } )
		root_part = make_func( self[ 'uvmm/domain/configure' ][ 'cmdline' ], default = handler._getattr( domain_info, 'cmdline', '' ), attributes = { 'width' : '250' } )
		kernel = make_func( self[ 'uvmm/domain/configure' ][ 'kernel' ], default = handler._getattr( domain_info, 'kernel', '' ), attributes = { 'width' : '250' } )
		bootdev_default = getattr( domain_info, 'boot', [ 'cdrom', 'hd' ] )
		bd_default = []
		if bootdev_default:
			for dev in bootdev_default:
				for key, descr in BootDeviceSelect.CHOICES:
					ud.debug( ud.ADMIN, ud.INFO, 'Domain configure: boot devices (compare): %s == %s' % ( key, dev ) )
					if key == str( dev ):
						bd_default.append( ( key, descr ) )
						break
		boot_dev.syntax.may_change = domain_is_off
		bootdevs = umcd.MultiValue( self[ 'uvmm/domain/configure' ][ 'bootdevs' ], fields = [ boot_dev ], default = bd_default, attributes = { 'width' : '200' } )
		bootdevs.syntax.may_change = domain_is_off
		# drive listing
		drive_sec = umcd.List( attributes = { 'width' : '100%' }, default_type = 'umc_list_element_narrow' )
		disk_list = umcd.List( attributes = { 'width' : '100%' }, default_type = 'umc_list_element_narrow' )
		disk_list.set_header( [ _( 'Type' ), _( 'Image' ), _( 'Size' ), _( 'Pool' ), '' ] )
		if domain_info and domain_info.disks:
			defaults = []
			overview_cmd = umcp.SimpleCommand( 'uvmm/domain/overview', options = copy.copy( object.options ) )
			storage_volumes = {}
			first = True
			for dev in domain_info.disks:
				remove_cmd = umcp.SimpleCommand( 'uvmm/drive/remove', options = copy.copy( object.options ) )
				remove_cmd.incomplete = True
				bootdev_cmd = umcp.SimpleCommand( 'uvmm/drive/bootdevice', options = copy.copy( object.options ) )
				remove_cmd.options[ 'disk' ] = None
				values = {}
				values[ 'type' ] = self._drive_name( dev.device )
				values[ 'image' ] = os.path.basename( dev.source )
				dir = os.path.dirname( dev.source )
				values[ 'pool' ] = dir
				try:
					storages
				except NameError:
					node_uri = self.uvmm.node_name2uri(object.options['node'])
					storages = self.uvmm.storage_pools(node_uri)
				for pool in storages:
					if pool.path == dir:
						values[ 'pool' ] = pool.name
						if not pool.name in storage_volumes:
							storage_volumes[ pool.name ] = self.uvmm.storage_pool_volumes(node_uri, pool.name)
						for vol in storage_volumes[ pool.name ]:
							if vol.source == dev.source:
								dev.size = vol.size
								break
						break
				if not dev.size:
					values[ 'size' ] = _( 'unknown' )
				else:
					values[ 'size' ] = MemorySize.num2str( dev.size )

				remove_cmd.options[ 'disk' ] = copy.copy( dev.source )
				remove_btn = umcd.LinkButton( _( 'Remove' ), actions = [ umcd.Action( remove_cmd ) ] )
				if domain_is_off:
					if not first:
						bootdev_cmd.options[ 'disk' ] = dev.source
						bootdev_btn = umcd.LinkButton( _( 'Set as boot device' ), actions = [ umcd.Action( bootdev_cmd, options = { 'disk' : dev.source } ), umcd.Action( overview_cmd ) ] )
						buttons = [ remove_btn, bootdev_btn ]
					else:
						buttons = [ remove_btn, ]
				else:
					buttons = []

				disk_list.add_row( [ values[ 'type' ], values[ 'image' ], values[ 'size' ], values[ 'pool' ], buttons ] )
				if domain_info.os_type == 'xen':
					first = False
		drive_sec.add_row( [disk_list ] )
		if domain_is_off:
			cmd = umcp.SimpleCommand('uvmm/drive/create', options=copy.copy(object.options))
			drive_sec.add_row([umcd.LinkButton(_('Add new drive'), actions=[umcd.Action(cmd),])])

		vnc_bool = False
		vnc_global = True
		vnc_keymap = 'de'
		old_passwd = ''
		if domain_info and domain_info.graphics:
			for gfx in domain_info.graphics:
				if gfx.type == uuv_node.Graphic.TYPE_VNC:
					if gfx.autoport:
						vnc_bool = True
					elif not gfx.autoport and gfx.port > 0:
						vnc_bool = True
					else:
						vnc_bool = False
					if gfx.listen != '0.0.0.0':
						vnc_global = False
					if gfx.passwd:
						old_passwd = gfx.passwd
					vnc_keymap = gfx.keymap
					break

		vnc = make_func( self[ 'uvmm/domain/configure' ][ 'vnc' ], default = vnc_bool, attributes = { 'width' : '250' } )
		kblayout = make_func( self[ 'uvmm/domain/configure' ][ 'kblayout' ], default = vnc_keymap, attributes = { 'width' : '250' } )
		vnc_global = make_func( self[ 'uvmm/domain/configure' ][ 'vnc_global' ], default = vnc_global, attributes = { 'width' : '250' } )
		vnc_passwd = make_func(self['uvmm/domain/configure']['vnc_passwd'], default=old_passwd, attributes={'width': '250'})

		content.add_row( [ name, os_widget ] )
		content.add_row( [ arch, '' ] )
		content.add_row( [ cpus, mac ] )
		content.add_row( [ memory, interface ] )

		content2 = umcd.List()
		content2.add_row( [ virt_tech ] )
		if domain_info.os_type == 'hvm':
			content2.add_row( [ bootdevs ] )
		else:
			content2.add_row( [ advkernelconf ] )
			content2.add_row( [ kernel ] )
			content2.add_row( [ ram_disk ] )
			content2.add_row( [ root_part ] )

		content2.add_row( [ umcd.Text( '' ) ] )

		content2.add_row( [ vnc, vnc_passwd ] )
		content2.add_row( [ vnc_global, kblayout ] )

		content2.add_row( [ umcd.Text( '' ) ] )

		ids = (name.id(), os_widget.id(), virt_tech.id(), arch.id(), cpus.id(), mac.id(), memory.id(), interface.id(), ram_disk.id(), root_part.id(), kernel.id(), vnc.id(), vnc_global.id(), vnc_passwd.id(), kblayout.id(), bootdevs.id())
		cfg_cmd = umcp.SimpleCommand( 'uvmm/domain/configure', options = object.options )
		overview_cmd = umcp.SimpleCommand( 'uvmm/domain/overview', options = object.options )

		sections = umcd.List()
		if not domain_is_off:
			sections.add_row( [ umcd.HTML( _( '<b>The settings of a virtual instance can just be modified if it is shut off.</b>' ) ) ] )
		if not domain_info:
			sections.add_row( [ umcd.Section( _( 'Drives' ), drive_sec, hideable = False, hidden = False, name = 'drives.newdomain' ) ] )
			sections.add_row( [ umcd.Section( _( 'Settings' ), content, hideable = False, hidden = True, name = 'settings.newdomain' ) ] )
			sections.add_row( [ umcd.Section( _( 'Extended Settings' ), content2, hideable = False, hidden = True, name = 'extsettings.newdomain' ) ] )
		else:
			sections.add_row( [ umcd.Section( _( 'Drives' ), drive_sec, hideable = True, hidden = False, name = 'drives.%s' % domain_info.name ) ] )
			sections.add_row( [ umcd.Section( _( 'Settings' ), content, hideable = True, hidden = True, name = 'settings.%s' % domain_info.name ) ] )
			sections.add_row( [ umcd.Section( _( 'Extended Settings' ), content2, hideable = True, hidden = True, name = 'extsettings.%s' % domain_info.name ) ] )
		if domain_is_off:
			sections.add_row( [ umcd.Cell( umcd.Button( _( 'Save' ), actions = [ umcd.Action( cfg_cmd, ids ), umcd.Action( overview_cmd ) ], default = True ), attributes = { 'align' : 'right' } ) ] )

		return sections

	def uvmm_domain_overview( self, object, finish = True ):
		"""Single domain overview."""
		ud.debug( ud.ADMIN, ud.INFO, 'Domain overview' )

		migrate = object.options.get( 'migrate' )
		if migrate == 'success':
			object.options[ 'node' ] = object.options[ 'dest' ]
		elif  migrate == 'failure':
			object.options[ 'node' ] = object.options[ 'source' ]
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'node', 'domain' ) )
		if not success:
			self.finished(object.id(), res)
			return
		self.domain_wizard.reset()

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		node_info, domain_info = self.uvmm.get_domain_info_ext( node_uri, object.options[ 'domain' ] )

		blind_table = umcd.List()

		if not domain_info:
			resync_cmd = umcd.Action( umcp.SimpleCommand( 'uvmm/daemon/restart', options = copy.copy( object.options ) ) )
			overview_cmd = umcd.Action( umcp.SimpleCommand( 'uvmm/domain/overview', options = copy.copy( object.options ) ) )
			resync = umcd.LinkButton( _( 'Resynchronize' ), actions = [ resync_cmd, overview_cmd ] )
			blind_table.add_row( [ _( 'The information about the virtual instance could not be retrieved. Clicking the refresh button will retry to collect the information. If this does not work a resynchronization can be triggered by clicking the following button.' ) ] )
			blind_table.add_row( [ umcd.Cell( resync, attributes = { 'align' : 'right' } ) ] )
		else:
			infos = umcd.List()
			w_status = [umcd.HTML('<b>%s</b>' % _('Status')), handler.STATES[domain_info.state]]
			w_os = [umcd.HTML('<b>%s</b>' % _('Operating System')), getattr(domain_info, 'annotations', {}).get('os', '' )]

			if domain_info.maxMem:
				pct = int( float( domain_info.curMem ) / domain_info.maxMem * 100 )
			else:
				pct = 0
			mem_usage = percentage( pct, label = '%s / %s' % ( MemorySize.num2str( domain_info.curMem ), MemorySize.num2str( domain_info.maxMem ) ), width = 130 )
			cpu_usage = percentage( float( domain_info.cputime[ 0 ] ) / 10, width = 130 )
			w_mem = [umcd.HTML('<b>%s</b>' % _('Memory usage')), mem_usage]
			w_cpu = [umcd.HTML('<b>%s</b>' % _('CPU usage')), cpu_usage]

			ops = umcd.List()
			buttons = self._create_domain_buttons( object, node_info, domain_info, overview = 'domain', operations = True )
			ops.add_row( buttons )

			tab = umcd.List()
			tab.add_row(w_status + w_cpu)
			tab.add_row(w_os + w_mem)

			tech = '%s-%s' % ( domain_info.domain_type, domain_info.os_type )
			blind_table.add_row( [ umcd.Section( _( 'Virtual instance %(domain)s - <i>%(tech)s</i>' ) % { 'domain' : domain_info.name, 'tech' : VirtTechSelect.MAPPING[ tech ] }, tab ) ] )
			blind_table.add_row( [ umcd.Cell( umcd.Section( _( 'Operations' ), ops ) ) ] )

			content = self._dlg_domain_settings( object, node_info, domain_info )
			blind_table.add_row( [ content ] )

		self.set_content( res, blind_table )
		if finish:
			self.finished(object.id(), res)
		return res

	def uvmm_domain_migrate( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Domain migrate' )
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'source', 'domain' ) )
		if not success:
			self.finished(object.id(), res)
			return

		content = umcd.List()
		if 'dest' in object.options:
			src_uri = self.uvmm.node_name2uri( object.options[ 'source' ] )
			dest_uri = self.uvmm.node_name2uri( object.options[ 'dest' ] )
			domain_info = self.uvmm.get_domain_info( src_uri, object.options[ 'domain' ] )
			ud.debug( ud.ADMIN, ud.INFO, 'Domain migrate: %s, %s, %s' % ( src_uri, dest_uri, domain_info ) )
			resp = self.uvmm.domain_migrate( src_uri, dest_uri, domain_info.uuid )
		else:
			domains = self.uvmm.get_group_info( object.options[ 'group' ] )
			dest_node_select.update_choices( [ domain_info.name for domain_info in domains ], object.options[ 'source' ] )
			content.set_header( [ umcd.Text( _( 'Migrate virtual instance %(domain)s from physical server %(source)s to:' ) % object.options ) ] )
			dest = umcd.make( self[ 'uvmm/domain/migrate' ][ 'dest' ] )
			content.add_row( [ dest, '' ] )
			opts = copy.copy( object.options )
			opts[ 'migrate' ] = 'success'
			cmd_success = umcd.Action( umcp.SimpleCommand( 'uvmm/domain/overview', options = opts ), [ dest.id(), ], status_range = umcd.Action.SUCCESS )
			opts2 = copy.copy( object.options )
			opts2[ 'migrate' ] = 'failure'
			cmd_failure = umcd.Action( umcp.SimpleCommand( 'uvmm/domain/overview', options = opts2 ), status_range = umcd.Action.FAILURE )

			content.add_row( [ '', umcd.Button( _( 'Migrate' ), actions = [ umcd.Action( umcp.SimpleCommand( 'uvmm/domain/migrate', options = object.options ), [ dest.id() ] ), cmd_success, cmd_failure ], default = True ) ] )
			res.dialog[ 0 ].set_dialog( content )
			resp = None

		if resp and self.uvmm.is_error( resp ):
			res.status( 301 )
			ud.debug( ud.ADMIN, ud.INFO, 'Domain migrate: error: %s' % str( resp.msg ) )
			self.finished( object.id(), res, report = str( resp.msg ) )
		else:
			self.finished( object.id(), res )

	def uvmm_domain_configure( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Domain configure' )
		res = umcp.Response( object )

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		node_info, domain_info = self.uvmm.get_domain_info_ext( node_uri, object.options[ 'domain' ] )
		if domain_info is None:
			domain_info = uuv_proto.Data_Domain()
		domain_info.name = object.options[ 'name' ]
		domain_info.domain_type, domain_info.os_type = object.options[ 'type' ].split( '-' )
		ud.debug( ud.ADMIN, ud.INFO, 'Domain configure: operating system: %s' % handler._getstr( object, 'os' ) )
		domain_info.annotations['os'] = handler._getstr( object, 'os' )
		domain_info.arch = object.options[ 'arch' ]
		ud.debug( ud.ADMIN, ud.INFO, 'Domain configure: architecture: %s' % domain_info.arch )
		domain_info.vcpus = int( object.options[ 'cpus' ] )
		# if para-virtualized machine ...
		if domain_info.domain_type == 'xen' and domain_info.os_type == 'linux':
			if object.options.get( 'advkernelconf', False ):
				domain_info.kernel = handler._getstr( object, 'kernel' )
				domain_info.cmdline = handler._getstr( object, 'cmdline' )
				domain_info.initrd = handler._getstr( object, 'initrd' )
			else:
				domain_info.bootloader = '/usr/bin/pygrub'
				domain_info.bootloader_args = '-q' # Bug #19249: PyGrub timeout
		domain_info.boot = handler._getstr( object, 'bootdevs' )
		domain_info.maxMem = MemorySize.str2num( object.options[ 'memory' ] )

		# interface
		# TODO: Allow unconnected hosts?
		try:
			iface = domain_info.interfaces[0]
		except (AttributeError, IndexError), e:
			iface = uuv_node.Interface()
			domain_info.interfaces.append( iface )
		iface.mac_address = handler._getstr( object, 'mac' )
		iface.source = handler._getstr( object, 'interface' )

		# graphics
		ud.debug( ud.ADMIN, ud.INFO, 'Configure Domain: graphics: %s' % object.options[ 'vnc' ] )
		if object.options[ 'vnc' ]:
			try:
				vncs = filter(lambda gfx: gfx.type == uuv_node.Graphic.TYPE_VNC, domain_info.graphics)
				gfx = vncs[0]
			except (AttributeError, IndexError), e:
				gfx = uuv_node.Graphic()
				domain_info.graphics.append( gfx )
			gfx.type = uuv_node.Graphic.TYPE_VNC
			gfx.keymap = object.options[ 'kblayout' ]
			gfx.passwd = object.options['vnc_passwd']
			if object.options[ 'vnc_global' ]:
				gfx.listen = '0.0.0.0'
			else:
				gfx.listen = None
			ud.debug( ud.ADMIN, ud.INFO, 'Configure Domain: graphics: %s' % str( gfx ) )
		else:
			# TODO: What about SDL, Spice, ...?
			non_vncs = filter(lambda gfx: gfx.type != uuv_node.Graphic.TYPE_VNC, domain_info.graphics)
			domain_info.graphics = non_vncs

		resp = self.uvmm.domain_configure( object.options[ 'node' ], domain_info )

		if self.uvmm.is_error( resp ):
			res.status( 301 )
			self.finished( object.id(), res, report = resp.msg )
		else:
			if resp.messages:
				res.status( 201 )
				msg = _( 'Some information of the virtual instance could not be saved!<br/>' ) + '<br/>'.join( [ str( _uvmm_locale( text ) ) for text in resp.messages ] )
			else:
				msg = ''
			self.finished( object.id(), res, report = msg )

	def uvmm_domain_state( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Domain State' )
		res = umcp.Response( object )

		ud.debug( ud.ADMIN, ud.INFO, 'Domain State: change to %s' % object.options[ 'state' ] )
		resp = self.uvmm.domain_set_state( object.options[ 'node' ], object.options[ 'domain' ], object.options[ 'state' ] )
		ud.debug( ud.ADMIN, ud.INFO, 'Domain State: changed to %s' % object.options[ 'state' ] )

		if self.uvmm.is_error( resp ):
			res.status( 301 )
			self.finished( object.id(), res, report = str( resp.msg ) )
		else:
			self.finished( object.id(), res )

	def uvmm_domain_create( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Domain create' )
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'node', 'domain' ) )
		if not success:
			self.finished(object.id(), res)
			return

		# user cancelled the wizard
		if object.options.get( 'action' ) == 'cancel':
			self.drive_wizard.reset()
			self.uvmm_node_overview( object )
			return

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		node_info = self.uvmm.get_node_info( node_uri )

		if not 'action' in object.options:
			self.domain_wizard.max_memory = node_info.phyMem
			self.domain_wizard.archs = set([t.arch for t in node_info.capabilities])
			self.domain_wizard.reset()

		result = self.domain_wizard.action( object, ( node_uri, node_info ) )

		# domain wizard finished?
		if self.domain_wizard.result():
			resp = self.uvmm.domain_configure( object.options[ 'node' ], self.domain_wizard.result() )
			object.options[ 'domain' ] = object.options[ 'name' ]
			if self.uvmm.is_error( resp ):
				# FIXME: something went wrong. We have to erase als 'critical' data and restart with the drive wizard part
				self.domain_wizard._result = None
				self.domain_wizard.current = 1
				self.domain_wizard.drives = []
				self.domain_wizard.action( object, ( node_uri, node_info ) )
				page = self.domain_wizard.setup( object )
				res.dialog[ 0 ].set_dialog( page )
				res.status( 301 )
				self.finished( object.id(), res, report = resp.msg )
			else:
				self.uvmm_domain_overview( object )
			return
		else:
			page = self.domain_wizard.setup( object )
			ud.debug( ud.ADMIN, ud.INFO, 'Domain create: dialog: %s' % str( page ) )
			res.dialog[ 0 ].set_dialog( page )

		if not result:
			res.status( 201 )
			report = result.text
		else:
			report = ''
		self.finished( object.id(), res, report = report )

	def uvmm_domain_remove_images( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Domain remove images' )
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'node', 'domain' ) )
		if not success:
			self.finished(object.id(), res)
			return

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		node_info, domain_info = self.uvmm.get_domain_info_ext( node_uri, object.options[ 'domain' ] )

		boxes = []
		lst = umcd.List()

		if domain_info.disks:
			lst.add_row([umcd.Cell(umcd.Text(_('When removing a virtual instance the disk images bind to it may be removed also. Please select the disks that should be remove with the virtual instance. Be sure that none of the images to be delete are used by any other instance.')), attributes={'colspan': '3'})])
			lst.add_row([''])
			defaults = []
			for disk in domain_info.disks:
				if not disk.source: continue
				static_options = { 'drives' : disk.source }
				default = disk.device != uvmmn.Disk.DEVICE_CDROM
				chk_button = umcd.Checkbox(static_options=static_options, default=default)
				chk_button.set_text( '%s: %s' % ( self._drive_name( disk.device ), disk.source ) )
				boxes.append( chk_button.id() )
				lst.add_row( [ umcd.Cell( umcd.Text( '' ), attributes = { 'width' : '10' } ), umcd.Cell( chk_button, attributes = { 'colspan' : '2' } ) ] )

		opts = copy.copy(object.options)
		opts['drives'] = []
		back = umcp.SimpleCommand('uvmm/domain/overview', options=opts)
		req = umcp.SimpleCommand('uvmm/domain/remove', options=opts)
		fail_overview_cmd = umcp.SimpleCommand('uvmm/domain/overview', options=opts)
		opts2 = copy.copy(object.options)
		del opts2['domain']
		success_overview_cmd = umcp.SimpleCommand('uvmm/node/overview', options=opts2)
		cancel = umcd.Button(_('Cancel'), actions=[umcd.Action(back)])
		button = umcd.Button(_('Remove'), actions=[umcd.Action(req, boxes), umcd.Action(success_overview_cmd, status_range=umcd.Action.SUCCESS), umcd.Action(fail_overview_cmd, status_range=umcd.Action.FAILURE)], default=True)
		lst.add_row([''])
		lst.add_row([umcd.Cell(cancel, attributes={'align': 'right', 'colspan': '2'}), umcd.Cell(button, attributes={'align': 'right'})])

		res.dialog[ 0 ].set_dialog( umcd.Section( _( 'Remove the virtual instance %(instance)s?' ) % { 'instance' : domain_info.name }, lst, hideable = False ) )
		self.finished(object.id(), res)

	def uvmm_domain_remove( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Domain remove' )
		res = umcp.Response( object )

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		domain_info = self.uvmm.get_domain_info( node_uri, object.options[ 'domain' ] )

		# shutdown machine before removing it
		self.uvmm.domain_set_state( object.options[ 'node' ], object.options[ 'domain' ], 'SHUTDOWN' )

		# remove domain
		resp = self.uvmm.domain_undefine( node_uri, domain_info.uuid, object.options[ 'drives' ] )

		if self.uvmm.is_error( resp ):
			res.status( 301 )
			self.finished( object.id(), res, report = _( 'Removing the instance <i>%(domain)s</i> failed' ) % { 'domain' : object.options[ 'domain' ] } )
		else:
			res.status( 201 )
			self.finished( object.id(), res, report = _( 'The instance <i>%(domain)s</i> was removed successfully' ) % { 'domain' : object.options[ 'domain' ] } )

	def uvmm_domain_snapshot_create(self, object):
		"""Create new snapshot of domain."""
		ud.debug(ud.ADMIN, ud.INFO, 'Domain snapshot create')
		node = object.options['node']
		domain = object.options['domain']
		try:
			snapshot_name = object.options['snapshot']
		except KeyError, e:
			snapshot_name = None
			object.incomplete = True

		if object.incomplete:
			(success, res) = TreeView.safely_get_tree(self.uvmm, object, ('group', 'node', 'domain'))
			if not success:
				self.finished(object.id(), res)
				return

			snapshot_cel = umcd.make(self['uvmm/domain/snapshot/create']['snapshot'], attributes={'colspan': '2'})

			opts = copy.copy(object.options)
			overview_cmd = umcp.SimpleCommand('uvmm/domain/overview', options=opts )

			cancel_act = [umcd.Action(overview_cmd)]
			cancel_btn = umcd.LinkButton(_('Cancel'), actions=cancel_act)
			cancel_cel = umcd.Cell(cancel_btn, attributes={'align': 'right', 'colspan': '2'})

			opts = copy.copy(object.options)
			create_cmd = umcp.SimpleCommand('uvmm/domain/snapshot/create', options=opts)

			create_act = [umcd.Action(create_cmd, [snapshot_cel.id()]), umcd.Action(overview_cmd)]
			create_btn = umcd.LinkButton(_('Create snapshot'), actions=create_act)
			create_cel = umcd.Cell(create_btn, attributes={'align': 'right'})

			lst = umcd.List()
			lst.add_row([umcd.Cell(umcd.Text(_('Enter the name for the snapshot')), attributes={'colspan': '3'})])
			lst.add_row([snapshot_cel,])
			lst.add_row([cancel_cel, create_cel])
			res.dialog[0].set_dialog(lst)
			self.finished(object.id(), res)
		else:
			res = umcp.Response(object)
			try:
				node_uri = self.uvmm.node_name2uri(node)
				domain_info = self.uvmm.get_domain_info(node_uri, domain)
				resp = self.uvmm.domain_snapshot_create(node_uri, domain_info, snapshot_name)
				res.status(201)
				report = _('The instance <i>%(domain)s</i> was snapshoted to <i>%(snapshot)s</i> successfully')
			except uvmmd.UvmmError, e:
				res.status(301)
				report = _('Snapshoting the instance <i>%(domain)s</i> to <i>%(snapshot)s</i> failed')
			values = {'domain': domain, 'snapshot': snapshot_name}
			self.finished(object.id(), res, report=report % values)

	def uvmm_domain_snapshot_revert(self, object):
		"""Revert to snapshot of domain."""
		ud.debug(ud.ADMIN, ud.INFO, 'Domain snapshot revert')
		node = object.options['node']
		domain = object.options['domain']
		snapshot_name = object.options['snapshot']

		res = umcp.Response(object)
		try:
			node_uri = self.uvmm.node_name2uri(node)
			domain_info = self.uvmm.get_domain_info(node_uri, domain)
			resp = self.uvmm.domain_snapshot_revert(node_uri, domain_info, snapshot_name)
			res.status(201)
			report = _('The instance <i>%(domain)s</i> was reverted to snapshot <i>%(snapshot)s</i> successfully')
		except uvmmd.UvmmError, e:
			res.status(301)
			report = _('Reverting to snapshot <i>%(snapshot)s</i> of instance <i>%(domain)s</i> failed')
		values = {'domain': domain, 'snapshot': snapshot_name}
		self.finished(object.id(), res, report=report % values)

	def uvmm_domain_snapshot_delete(self, object):
		"""Delete snapshot of domain."""
		ud.debug(ud.ADMIN, ud.INFO, 'Domain snapshot delete')
		node = object.options['node']
		domain = object.options['domain']
		snapshot_name = object.options['snapshot']

		res = umcp.Response(object)
		try:
			node_uri = self.uvmm.node_name2uri(node)
			domain_info = self.uvmm.get_domain_info(node_uri, domain)
			resp = self.uvmm.domain_snapshot_delete(node_uri, domain_info, snapshot_name)
			res.status(201)
			report = _('The snapshot <i>%(snapshot)s of instance <i>%(domain)s</i> was deleted successfully')
		except uvmmd.UvmmError, e:
			res.status(301)
			report = _('Deleting the snapshot <i>%(snapshot)s</i> of instance <i>%(domain)s</i> failed')
		values = {'domain': domain, 'snapshot': snapshot_name}
		self.finished(object.id(), res, report=report % values)

	def uvmm_drive_create( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Drive create' )
		( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'node', 'domain' ) )
		if not success:
			self.finished(object.id(), res)
			return
		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		node_info = self.uvmm.get_node_info( node_uri )

		ud.debug( ud.ADMIN, ud.INFO, 'Drive create: action: %s' % str( object.options.get( 'action' ) ) )
		# user cancelled the wizard
		if object.options.get( 'action' ) == 'cancel':
			self.drive_wizard.reset()
			del object.options[ 'action' ]
			self.uvmm_domain_overview( object )
			return

		# starting the wizard
		if not 'action' in object.options:
			self.drive_wizard.reset()
			self.drive_wizard.domain_name = object.options['domain']
			self.drive_wizard.blacklist = [] # does query domains

		result = self.drive_wizard.action( object, ( node_uri, node_info ) )

		# domain wizard finished?
		if self.drive_wizard.result():
			new_disk = self.drive_wizard.result()
			domain_info = self.uvmm.get_domain_info( node_uri, object.options[ 'domain' ] )
			domain_info.disks.append( new_disk )
			resp = self.uvmm.domain_configure( object.options[ 'node' ], domain_info )
			new_disk = self.drive_wizard.reset()
			if self.uvmm.is_error( resp ):
				res = self.uvmm_domain_overview( object, finish = False )
				res.status( 301 )
				self.finished( object.id(), res, report = resp.msg )
			else:
				self.uvmm_domain_overview( object )
			return
		# navigating in the wizard ...
		page = self.drive_wizard.setup( object )
		res.dialog[ 0 ].set_dialog( page )
		if not result:
			res.status( 201 )
			report = result.text
		else:
			report = ''
		self.finished( object.id(), res, report = report )

	def uvmm_drive_remove( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Drive remove' )
		res = umcp.Response( object )

		if object.incomplete:
			ud.debug( ud.ADMIN, ud.INFO, 'drive remove' )
			( success, res ) = TreeView.safely_get_tree( self.uvmm, object, ( 'group', 'node', 'domain' ) )
			if not success:
				self.finished(object.id(), res)
				return
			# remove domain
			# if the attached drive could be removed successfully the user should be ask, if the image should be removed
			node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
			node_info, domain_info = self.uvmm.get_domain_info_ext(node_uri, object.options['domain'])
			for disk in domain_info.disks:
				if disk.source == object.options['disk']:
					break
			is_shared_image = disk.device == uvmmn.Disk.DEVICE_CDROM
			lst = umcd.List()

			lst.add_row( [ umcd.Cell( umcd.Text( _( 'The drive will be detached from the virtual instance. Additionally the associated image %(image)s may be deleted permanently. Should this be done also?' ) % { 'image' : object.options[ 'disk' ] } ), attributes = { 'colspan' : '3' } ) ] )
			opts = copy.copy( object.options )
			overview = umcp.SimpleCommand( 'uvmm/domain/overview', options = opts )
			opts = copy.copy( object.options )
			opts[ 'drive-remove' ] = True
			remove = umcp.SimpleCommand( 'uvmm/drive/remove', options = opts )
			opts = copy.copy( object.options )
			opts[ 'drive-remove' ] = False
			detach = umcp.SimpleCommand( 'uvmm/drive/remove', options = opts )
			no = umcd.Button(_('No'), actions=[umcd.Action(detach), umcd.Action(overview)], default=is_shared_image)
			yes = umcd.Button(_('Yes'), actions=[umcd.Action(remove), umcd.Action(overview)], default=not is_shared_image)
			lst.add_row( [ '' ] )
			lst.add_row( [ umcd.Cell( no, attributes = { 'align' : 'right', 'colspan' : '2' } ), umcd.Cell( yes, attributes = { 'align' : 'right' } ) ] )
			res.dialog[ 0 ].set_dialog( lst )
			self.finished(object.id(), res)
		else:
			node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
			domain_info = self.uvmm.get_domain_info( node_uri, object.options[ 'domain' ] )
			new_disks = []
			for dev in domain_info.disks:
				if dev.source != object.options[ 'disk' ]:
					new_disks.append( dev )
			domain_info.disks = new_disks
			resp = self.uvmm.domain_configure( object.options[ 'node' ], domain_info )

			if self.uvmm.is_error( resp ):
				res.status( 301 )
				self.finished( object.id(), res, report = _( 'Detaching the drive <i>%(drive)s</i> failed' ) % { 'drive' : os.path.basename( object.options[ 'disk' ] ) } )
				return

			if object.options.get( 'drive-remove', False ):
				resp = self.uvmm.storage_volumes_destroy( node_uri, [ object.options[ 'disk' ], ] )

				if not resp:
					res.status( 301 )
					self.finished( object.id(), res, report = _( 'Removing the image <i>%(disk)s</i> failed. It must be removed manually.' ) % { 'drive' : os.path.basename( object.options[ 'disk' ] ) } )
					return
				res.status( 201 )
				self.finished( object.id(), res, report = _( 'The drive <i>%(drive)s</i> was detached and removed successfully' ) % { 'drive' : os.path.basename( object.options[ 'disk' ] ) } )
			res.status( 201 )
			self.finished( object.id(), res, report = _( 'The drive <i>%(drive)s</i> was detached successfully' ) % { 'drive' : os.path.basename( object.options[ 'disk' ] ) } )

	def uvmm_drive_bootdevice( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Drive boot device' )
		res = umcp.Response( object )

		node_uri = self.uvmm.node_name2uri( object.options[ 'node' ] )
		domain_info = self.uvmm.get_domain_info( node_uri, object.options[ 'domain' ] )
		new_disks = []
		for dev in domain_info.disks:
			if dev.source != object.options[ 'disk' ]:
				new_disks.append( dev )
			else:
				new_disks.insert( 0, dev )
		domain_info.disks = new_disks
		resp = self.uvmm.domain_configure( object.options[ 'node' ], domain_info )

		if self.uvmm.is_error( resp ):
			res.status( 301 )
			self.finished( object.id(), res, report = _( 'Setting the drive <i>%(drive)s</i> as boot device as failed' ) % { 'drive' : os.path.basename( object.options[ 'disk' ] ) } )
		else:
			self.finished( object.id(), res )

	def uvmm_daemon_restart( self, object ):
		ud.debug( ud.ADMIN, ud.INFO, 'Drive boot device' )
		res = umcp.Response( object )

		child = notifier.popen.run( '/usr/sbin/invoke-rc.d univention-virtual-machine-manager-node-common restart', timeout = 10000, stdout = False, stderr = False, shell = False )
		if child.exitcode == None: # failed to restart libvirt
			res.status( 301 )
			self.finished( object.id(), res, report = _( 'Resynchronisation has failed!' ) )
			return

		time.sleep( 5 )
		self.finished( object.id(), res )
