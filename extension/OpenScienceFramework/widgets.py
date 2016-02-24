# -*- coding: utf-8 -*-
"""
This file is part of OpenSesame.

OpenSesame is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenSesame is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

This module is distributed under the Apache v2.0 License.
You should have received a copy of the Apache v2.0 License
along with this module. If not, see <http://www.apache.org/licenses/>.
"""
# Python3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import logging

# QT classes
from qtpy import QtGui, QtCore, QtWebKit, QtWidgets
# OSF connection interface
import connection as osf
# For performing HTTP requests
import requests

class LoginWindow(QtWebKit.QWebView):
	""" A Login window for the OSF """
	# Login event is emitted after successfull login
	
	def __init__(self):
		super(LoginWindow, self).__init__()
		
		# Create Network Access Manager to listen to all outgoing
		# HTTP requests. Necessary to work around the WebKit 'bug' which
		# causes it drop url fragments, and thus the access_token that the
		# OSF Oauth system returns
		self.nam = self.page().networkAccessManager()
		
		# Connect event that is fired after an URL is changed
		# (does not fire on 301 redirects, hence the requirement of the NAM)
		self.urlChanged.connect(self.check_URL)
	
		# Connect event that is fired if a HTTP request is completed.
		self.nam.finished.connect(self.checkResponse)
		
	def checkResponse(self,reply):
		request = reply.request()
		# Get the HTTP statuscode for this response
		statuscode = reply.attribute(request.HttpStatusCodeAttribute)
		# The accesstoken is given with a 302 statuscode to redirect
		
		if statuscode == 302:
			redirectUrl = reply.attribute(request.RedirectionTargetAttribute)
			if redirectUrl.hasFragment():
				r_url = redirectUrl.toString()
				if osf.redirect_uri in r_url:
					logging.info("Token URL: {}".format(r_url))
					self.token = osf.parse_token_from_url(r_url)
					if self.token:
						self.close()
		
	def check_URL(self, url):
		new_url = url.toEncoded()
		
		if not osf.base_url in new_url and not osf.redirect_uri in new_url:
			logging.warning("URL CHANGED: Unexpected url: {}".format(url))
			
class UserBadge(QtWidgets.QWidget):
	""" A Widget showing the logged in user """
	
	# Class variables
	
	# Size of avatar and osf logo display image
	image_size = QtCore.QSize(50,50)
	# Login and logout events
	logout_request = QtCore.pyqtSignal()
	login_request = QtCore.pyqtSignal()
	# button texts
	login_text = "Log in to OSF"
	logout_text = "Log out"
	
	def __init__(self):
		super(UserBadge, self).__init__()

		# Set up general window
		self.resize(200,40)
		self.setWindowTitle("User badge")
		# Set Window icon
		osf_logo = os.path.abspath('../../resources/img/cos-white2.png')

		if not os.path.isfile(osf_logo):
			print("ERROR: OSF logo not found at {}".format(osf_logo))

		self.osf_logo_pixmap = QtGui.QPixmap(osf_logo)	.scaled(self.image_size)
		
		osf_icon = QtGui.QIcon(osf_logo)
		self.setWindowIcon(osf_icon)
		
		## Set up labels
		# User's name
		self.user_name = QtGui.QLabel()
		# User's avatar
		self.avatar = QtGui.QLabel()
		
		# Login button
		self.statusbutton = QtGui.QPushButton(self)
		self.statusbutton.clicked.connect(self.__handle_click)
		
		# Determine content of labels:
		self.check_user_status()
		
		# Set up layout
		grid = QtGui.QGridLayout()
		grid.setSpacing(5)
		grid.addWidget(self.avatar,1,0)
		
		login_grid = QtGui.QGridLayout()
		login_grid.setSpacing(5)
		login_grid.addWidget(self.user_name,1,1)
		login_grid.addWidget(self.statusbutton,2,1)
		
		grid.addLayout(login_grid,1,1)
		self.setLayout(grid)
	
	def __handle_click(self):
		button = self.sender()
		logging.info("Button {} clicked".format(button.text()))
		if button.text() == self.login_text:
			self.login_request.emit()
		elif button.text() == self.logout_text:
			button.setText("Logging out...")
			QtCore.QCoreApplication.instance().processEvents()
			self.logout_request.emit()
		
	def handle_login(self):
		self.check_user_status()
			
	def handle_logout(self):
		self.check_user_status()			
			
	def check_user_status(self):
		if osf.is_authorized():
			# Request logged in user's info
			self.user = osf.get_logged_in_user()
			# Get user's name
			full_name = self.user["data"]["attributes"]["full_name"]
			# Download avatar image from the specified url
			avatar_url = self.user["data"]["links"]["profile_image"]
			avatar_img = requests.get(avatar_url).content
			pixmap = QtGui.QPixmap()
			pixmap.loadFromData(avatar_img)
			pixmap = pixmap.scaled(self.image_size)
			
			# Update sub-widgets
			self.user_name.setText(full_name)
			self.avatar.setPixmap(pixmap)
			self.statusbutton.setText(self.logout_text)
		else:
			self.user = None
			self.user_name.setText("")
			self.avatar.setPixmap(self.osf_logo_pixmap)
			self.statusbutton.setText(self.login_text)
			
			
class Explorer(QtWidgets.QTreeWidget):
	""" A tree represntation of project and files on the OSF for the current user
	in a treeview """
	
	def __init__(self, *args, **kwars):
		super(Explorer, self).__init__(*args, **kwars)
		
		# Set up general window
		self.resize(400,500)
		self.setWindowTitle("Project explorer")
		
		# Set Window icon
		osf_logo = os.path.abspath('../../resources/img/cos-white2.png')
		if not os.path.isfile(osf_logo):
			print("ERROR: OSF logo not found at {}".format(osf_logo))
		osf_icon = QtGui.QIcon(osf_logo)
		self.setWindowIcon(osf_icon)
		
		# Set column labels
		self.setHeaderLabels(["Name","Kind"])

	def populate_tree(self):
		osf_response = osf.get_user_projects()
		
		treeItems = []
		for project in osf_response["data"]:
			item = QtWidgets.QTreeWidgetItem(
				self.invisibleRootItem(),
				[
					project["attributes"]["title"],
					project["attributes"]["category"]
				]
			)
			repos = self.get_repos(project["id"])			
			item.addChildren(repos)
			treeItems.append(item)			
		self.addTopLevelItems(treeItems)
		
	def get_repos(self, node_id):
		osf_response = osf.get_project_repos(node_id)
		repos = []
		for repo in osf_response["data"]:
			item = QtWidgets.QTreeWidgetItem(
				[
					repo["attributes"]["name"],
					repo["attributes"]["kind"]
				]
			)
			files = self.get_repo_files(repo["attributes"]["node"], repo["attributes"]["name"])
			item.addChildren(files)
			repos.append(item)
		return repos
		
	def get_repo_files(self,node_id,repo_name):
		osf_response = osf.get_repo_files(node_id, repo_name)
		files = []
		for entry in osf_response["data"]:
			if entry["attributes"]["kind"] == "file":
				item = QtWidgets.QTreeWidgetItem(
					[
						entry["attributes"]["name"],
						entry["attributes"]["kind"]
					]
				)
				files.append(item)
		return files
			
		
	def handle_login(self):
		self.populate_tree()
		
	def handle_logout(self):
		self.clear()
		
		
		
		
		
		
		
		
		
		
		
		
		

		
		
	
	