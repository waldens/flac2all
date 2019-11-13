# -*- coding: utf-8 -*-

import datetime

from termcolor import cprint


class console():
	def __init__(self, stderr=True):
		self.stderr = stderr

	def _genmsg(self, msg):
		return "UTC,%s: %s" % (
			datetime.datetime.utcnow().isoformat(),
			msg
		)

	def status(self, msg):
		if self.stderr:
			cprint(self._genmsg(msg), "cyan")

	def info(self, msg):
		if self.stderr:
			cprint(self._genmsg(msg), "magenta")

	def ok(self, msg):
		if self.stderr:
			cprint(self._genmsg(msg), "green")

	def warn(self, msg):
		if self.stderr:
			cprint(self._genmsg(msg), "yellow")

	def crit(self, msg):
		if self.stderr:
			cprint(self._genmsg(msg), "red")