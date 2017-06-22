import socket
import hashlib
import re
import os
import json
import threading

class Penguin:
	def __init__(self, id, name, clothes, x, y):
		self.id = id
		self.name = name
		self.clothes = clothes
		self.x = x
		self.y = y
	
	@classmethod
	def from_player(cls, player):
		player = player.split('|')
		id = int(player[0])
		name = player[1]
		clothes = {}
		# ??? = player[2]
		info = ["color", "head", "face", "neck", "body", "hand", "feet", "pin", "background"]
		for i in range(len(info)):
			if player[i + 3]:
				clothes[info[i]] = int(player[i + 3])
		x = int(player[12])
		y = int(player[13])
		return cls(id, name, clothes, x, y)

class Client:
	def __init__(self, ip, login_port, game_port, log = False):
		self.ip = ip
		self.login_port = login_port
		self.game_port = game_port
		self.log = log
		self.buf = ""
		self.internal_room_id = -1
		self.id = -1
		self.coins = -1
		self.current_room = -1
		self.penguins = {}
		self.followed = None

	@staticmethod
	def swapped_md5(password, encrypted = False):
		if not encrypted:
			password = hashlib.md5(password).hexdigest()
		password = password[16:32] + password[0:16]
		return password

	def _send(self, data):
		if self.log:
			print "# SEND: " + str(data)
		self.sock.send(data + chr(0))

	def _receive(self):
		try:
			while not chr(0) in self.buf:
				self.buf += self.sock.recv(4096)
		except:
			return None
		i = self.buf.index(chr(0)) + 1
		message = self.buf[:i]
		self.buf = self.buf[i:]
		if self.log:
			print "# RECEIVE: " + str(message)
		return message

	def _packet(self):
		buf = self._receive()
		if not buf:
			return None
		if buf.startswith("%"):
			packet = buf.split('%')
			if packet[2] == "e":
				self._error(packet)
			return packet
		raise Exception("Invalid packet")

	def _error(self, packet):
		filename = os.path.join(os.path.dirname(__file__), "json/errors.json")
		with open(filename) as file:
			data = json.load(file)
		code = int(packet[4])
		print "Error #" + str(code) + ": " + data[str(code)]

	def _ver_check(self, ver = 153):
		if self.log:
			print "Sending 'verChk' request..."
		self._send('<msg t="sys"><body action="verChk" r="0"><ver v="' + str(ver) + '"/></body></msg>')
		buf = self._receive()
		if 'apiOK' in buf:
			if self.log:
				print "Received 'apiOK' response."
			return True
		if 'apiKO' in buf:
			if self.log:
				print "Received 'apiKO' response."
			return False
		raise Exception("Invalid response")

	def _key(self):
		if self.log:
			print "Sending rndK request..."
		self._send('<msg t="sys"><body action="rndK" r="-1"></body></msg>')
		buf = self._receive()
		if 'rndK' in buf:
			key = re.search("<k>(<!\[CDATA\[)?(.*?)(\]\]>)?<\/k>", buf).group(2)
			if self.log:
				print "Received key: " + key
			return key
		raise Exception("Invalid response")

	def _login(self, user, password, encrypted, ver):
		if self.log:
			print "Logging in..."
		self._ver_check(ver)
		rndk = self._key()
		hash = self.swapped_md5(self.swapped_md5(password, encrypted).upper() + rndk + "Y(02.>'H}t\":E1")
		self._send('<msg t="sys"><body action="login" r="0"><login z="w1"><nick><![CDATA[' + user + ']]></nick><pword><![CDATA[' + hash + ']]></pword></login></body></msg>')
		packet = self._packet()
		if not packet or packet[2] == "e":
			return packet, False
		while packet[2] != "l":
			packet = self._packet()
			if packet[2] == "e":
				return packet, False
		if self.log:
			print "Logged in."
		return packet, True

	def _join_server(self, user, login_key, ver):
		if self.log:
			print "Joining server..."
		self._ver_check(ver)
		rndk = self._key()
		hash = self.swapped_md5(login_key + rndk) + login_key
		self._send('<msg t="sys"><body action="login" r="0"><login z="w1"><nick><![CDATA[' + user + ']]></nick><pword><![CDATA[' + hash + ']]></pword></login></body></msg>')
		packet = self._packet()
		if packet and packet[2] == "l":
			self._send("%xt%s%j#js%" + str(self.internal_room_id) + "%" + str(self.id) + "%" + login_key + "%en%")
			packet = self._packet()
			if packet[2] == "js":
				if self.log:
					print "Joined server."
				return packet, True
		return packet, False
		
	def _get_id(self, name):
		for penguin in self.penguins.values():
			if penguin.name == name:
				return penguin.id
		return 0
		
	def _game(self):
		thread = threading.Thread(target = self._heartbeat)
		thread.start()
		while True:
			packet = self._packet()
			if not packet:
				break
			op = packet[2]
			if op == "e":
				pass
			if op == "h":
				pass
			elif op == "lp":
				penguin = Penguin.from_player(packet[4])
				self.penguins[penguin.id] = penguin
				self.coins = int(packet[5])
				safemode = packet[6] == '1'
				# egg_timer = int(packet[7])
				login_time = long(packet[8])
				age = int(packet[9])
				# banned_age = int(packet[10])
				play_time = int(packet[11])
				if packet[12]:
					member_left = int(packet[12])
				else:
					member_left = 0
				timezone = int(packet[13])
				# opened_playcard = packet[14] == '1'
				# saved_map_category = int(packet[15])
				# status_field = int(packet[16])
			elif op == "ap":
				penguin = Penguin.from_player(packet[4])
				self.penguins[penguin.id] = penguin
			elif op == "jr":
				self.internal_room_id = int(packet[3])
				self.penguins.clear()
				self.current_room = int(packet[4])
				for i in packet[5:-1]:
					penguin = Penguin.from_player(i)
					self.penguins[penguin.id] = penguin
			elif op == "rp":
				id = int(packet[4])
				penguin = self.penguins.pop(id)
				if self.followed and id == self.followed["id"]:
					self._send("%xt%s%b#bf%" + str(self.internal_room_id) + "%" + str(id) + "%")
			elif op == "br":
				id = int(packet[4])
				name = packet[5]
				if raw_input("Buddy with " + name + "? [y/n]") == "y":
					self._send("%xt%s%b#ba%" + str(self.internal_room_id) + "%" + str(id) + "%")
			elif op == "bf":
				room = int(packet[4])
				id = int(packet[6])
				if self.followed and id == self.followed["id"]:
					self.room(room)
			elif op == "upc":
				id = int(packet[4])
				penguin = self.penguins[id]
				color = int(packet[5])
				penguin.clothes["color"] = color
				if self.followed and id == self.followed["id"]:
					self.update_color(color)
			elif op == "uph":
				id = int(packet[4])
				penguin = self.penguins[id]
				head = int(packet[5])
				penguin.clothes["head"] = head
				if self.followed and id == self.followed["id"]:
					self.update_head(head)
			elif op == "upf":
				id = int(packet[4])
				penguin = self.penguins[id]
				face = int(packet[5])
				penguin.clothes["face"] = face
				if self.followed and id == self.followed["id"]:
					self.update_face(face)
			elif op == "upn":
				id = int(packet[4])
				penguin = self.penguins[id]
				neck = int(packet[5])
				penguin.clothes["neck"] = neck
				if self.followed and id == self.followed["id"]:
					self.update_neck(neck)
			elif op == "upb":
				id = int(packet[4])
				penguin = self.penguins[id]
				body = int(packet[5])
				penguin.clothes["body"] = body
				if self.followed and id == self.followed["id"]:
					self.update_body(body)
			elif op == "upa":
				id = int(packet[4])
				penguin = self.penguins[id]
				hand = int(packet[5])
				penguin.clothes["hand"] = hand
				if self.followed and id == self.followed["id"]:
					self.update_hand(hand)
			elif op == "upe":
				id = int(packet[4])
				penguin = self.penguins[id]
				feet = int(packet[5])
				penguin.clothes["feet"] = feet
				if self.followed and id == self.followed["id"]:
					self.update_feet(feet)
			elif op == "upl":
				id = int(packet[4])
				penguin = self.penguins[id]
				pin = int(packet[5])
				penguin.clothes["pin"] = pin
				if self.followed and id == self.followed["id"]:
					self.update_pin(pin)
			elif op == "upp":
				id = int(packet[4])
				penguin = self.penguins[id]
				background = int(packet[5])
				penguin.clothes["background"] = background
				if self.followed and id == self.followed["id"]:
					self.update_background(background)
			elif op == "sp":
				id = int(packet[4])
				penguin = self.penguins[id]
				penguin.x = int(packet[5])
				penguin.y = int(packet[6])
				if self.followed and id == self.followed["id"]:
					self.walk(penguin.x + self.followed["x"], penguin.y + self.followed["y"])
			elif op == "sa":
				id = int(packet[4])
				action = int(packet[5])
				if self.followed and id == self.followed["id"]:
					self._action(action)
			elif op == "sf":
				id = int(packet[4])
				frame = int(packet[5])
				if self.followed and id == self.followed["id"]:
					self._frame(frame)
			elif op == "sb":
				id = int(packet[4])
				x = int(packet[5])
				y = int(packet[6])
				if self.followed and id == self.followed["id"]:
					self.snowball(x, y)
			elif op == "sm":
				id = int(packet[4])
				message = packet[5]
				if self.followed and id == self.followed["id"]:
					self.say(message, False)
			elif op == "ss":
				id = int(packet[4])
				message = packet[5]
				if self.followed and id == self.followed["id"]:
					self.say(message, True)
			elif op == "sj":
				id = int(packet[4])
				joke = int(packet[5])
				if self.followed and id == self.followed["id"]:
					self.joke(joke)
			elif op == "se":
				id = int(packet[4])
				emote = int(packet[5])
				if self.followed and id == self.followed["id"]:
					self.emote(emote)
			elif op == "ai":
				id = int(packet[4])
				coins = int(packet[5])
				cost = self.coins - coins
				self.coins = coins
				print "Added item " + str(id) + " (cost " + str(cost) + " coins)"
			elif self.log:
				print "# UNKNOWN OPCODE: " + op
				
	def _heartbeat(self):
		threading.Timer(600, self._heartbeat)
		self._send("%xt%s%u#h%" + str(self.internal_room_id) + "%")

	def connect(self, user, password, encrypted = False, ver = 153):
		if self.log:
			print "Connecting to " + self.ip + ":" + str(self.login_port) + "..."
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect((self.ip, self.login_port))
			
		packet, ok = self._login(user, password, encrypted, ver)
		if not ok:
			return int(packet[4])
		self.id = int(packet[4])
		login_key = packet[5]
		
		if self.log:
			print "Connecting to " + self.ip + ":" + str(self.game_port) + "..."
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect((self.ip, self.game_port))
		
		packet, ok = self._join_server(user, login_key, ver)
		if not ok:
			return int(packet[4])
		thread = threading.Thread(target = self._game)
		thread.start()
		return 0

	def room(self, id, x = 0, y = 0):
		if self.log:
			print "Going to room " + str(id) + "..."
		self._send("%xt%s%j#jr%" + str(self.internal_room_id) + "%" + str(id) + "%" + str(x) + "%" + str(y) + "%")
		
	def update_color(self, id):
		if self.log:
			print "Changing color to " + str(id) + "..."
		self._send("%xt%s%s#upc%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_head(self, id):
		if self.log:
			print "Changing head item to " + str(id) + "..."
		self._send("%xt%s%s#uph%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_face(self, id):
		if self.log:
			print "Changing face item to " + str(id) + "..."
		self._send("%xt%s%s#upf%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_neck(self, id):
		if self.log:
			print "Changing neck item to " + str(id) + "..."
		self._send("%xt%s%s#upn%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_body(self, id):
		if self.log:
			print "Changing body item to " + str(id) + "..."
		self._send("%xt%s%s#upb%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_hand(self, id):
		if self.log:
			print "Changing hand item to " + str(id) + "..."
		self._send("%xt%s%s#upa%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_feet(self, id):
		if self.log:
			print "Changing feet item to " + str(id) + "..."
		self._send("%xt%s%s#upe%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_pin(self, id):
		if self.log:
			print "Changing pin to " + str(id) + "..."
		self._send("%xt%s%s#upl%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def update_background(self, id):
		if self.log:
			print "Changing background to " + str(id) + "..."
		self._send("%xt%s%s#upp%" + str(self.internal_room_id) + "%" + str(id) + "%")
		
	def walk(self, x, y):
		if self.log:
			print "Walking to (" + str(x) + ", " + str(y) + ")..."
		self._send("%xt%s%u#sp%" + str(self.id) + "%" + str(x) + "%" + str(y) + "%")
		
	def _action(self, id):
		self._send("%xt%s%u#sa%" + str(self.internal_room_id) + "%" + str(id) + "%")
		
	def _frame(self, id):
		self._send("%xt%s%u#sf%" + str(self.internal_room_id) + "%" + str(id) + "%")
		
	def dance(self):
		if self.log:
			print "Dancing..."
		self._frame(26)

	def wave(self):
		if self.log:
			print "Waving..."
		self._action(25)
		
	def sit(self, dir = "s"):
		if self.log:
			print "Sitting..."
		dirs = {
			"se": 24,
			"e": 23,
			"ne": 22,
			"n": 21,
			"nw": 20,
			"w": 19,
			"sw": 18,
			"s": 17
		}
		if dir in dirs:
			self._frame(dirs[dir])
		else:
			self._frame(dirs["s"])

	def snowball(self, x, y):
		if self.log:
			print "Throwing snowball to (" + str(x) + ", " + str(y) + ")..."
		self._send("%xt%s%u#sb%" + str(self.internal_room_id) + "%" + str(x) + "%" + str(y) + "%")

	def say(self, message, safe = False):
		if self.log:
			print "Saying '" + message + "'..."
		if safe:
			self._send("%xt%s%u#ss%" + str(self.internal_room_id) + "%" + message + "%")
		else:
			self._send("%xt%s%m#sm%" + str(self.internal_room_id) + "%" + str(self.id) + "%" + message + "%")

	def joke(self, joke):
		if self.log:
			print "Saying joke " + str(joke) + "..."
		self._send("%xt%s%u#sj%" + str(self.id) + "%" + str(joke) + "%")
		
	def emote(self, emote):
		if self.log:
			print "Saying emote " + str(emote) + "..."
		self._send("%xt%s%u#se%" + str(self.internal_room_id) + "%" + str(emote) + "%")
		
	def add_item(self, id):
		if self.log:
			print "Adding item " + str(id) + "..."
		self._send("%xt%s%i#ai%" + str(self.internal_room_id) + "%" + str(id) + "%")
		
	def buddy(self, id):
		if self.log:
			print "Sending buddy request to " + str(id) + "..."
		self._send("%xt%s%b#br%" + str(self.internal_room_id) + "%" + str(id) + "%")

	def follow(self, name, offset_x = 0, offset_y = 0):
		if self.log:
			print "Following " + name + "..."
		id = self._get_id(name)
		if id:
			self.buddy(id)
			self.followed = {"id": id, "x": offset_x, "y": offset_y}
			penguin = self.penguins[id]
			self.walk(penguin.x + offset_x, penguin.y + offset_y)

	def unfollow(self):
		if self.log:
			print "Unfollowing..."
		self.followed = None

	def logout(self):
		if self.log:
			print "Logging out..."
		self.sock.shutdown(socket.SHUT_RDWR)
		self.sock.close()