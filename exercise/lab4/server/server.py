# coding=utf-8
import argparse
import json
import sys
from threading import Lock, Thread
import time
import traceback
import bottle
from bottle import Bottle, request, template, run, static_file
import requests
from byzantine_behavior import compute_byzantine_vote_round1,compute_byzantine_vote_round2
# ------------------------------------------------------------------------------------------------------

class Blackboard():

	def __init__(self):
		self.content = ""
		self.lock = Lock() # use lock when you modify the content


	def get_content(self):
		with self.lock:
			cnt = self.content
		return cnt


	def set_content(self, new_content):
		with self.lock:
			self.content = new_content
		return


# ------------------------------------------------------------------------------------------------------
class Server(Bottle):

	def __init__(self, ID, IP, servers_list):
		super(Server, self).__init__()
		self.blackboard = Blackboard()
		self.id = int(ID)
		self.ip = str(IP)
		self.servers_list = servers_list
		self.board = dict()

		#Initial Case We have 3 Loyals and 1 Byzantine
		self.loyal_members = len(self.servers_list)
		self.byzantine_member = 0
		self.total_members = len(self.servers_list)

		self.votes = {}
		self.generals = {}
		self.transmitted = False
		self.byzantine = False
		self.counter_byz = 0
		self.byzantine_list = []
		self.mode = ["Attack", "Retreat", "Unknown"]
		self.votes_tied = False
		self.my_vote = ''


		# list all REST URIs
		# if you add new URIs to the server, you need to add them here
		self.post('/attack', callback=self.vote_attack)
		self.post('/retreat', callback=self.vote_retreat)
		self.post('/byzantine', callback=self.vote_byzantine)
		self.post('/propagate', callback=self.propagate_votes)
		self.post('/exchange', callback=self.exchange_votes)
		self.get('/result', callback=self.show_result)
		# self.post('/tie_breaker', callback=self.tie_breaker)
		self.route('/', callback=self.index)

		# self.post('/find/byzantine', callback=self.find_byzantine)
		# self.post('/byzantine/resp', callback=self.byzantine_resp)
		#self.post('/sendb', callback=self.sendb)
		self.post('/', callback=self.post_index)
		# self.post('/look/for/byzantine', callback=self.look_for_byzantine)



		# we give access to the templates elements
		self.get('/templates/<filename:path>', callback=self.get_template)
		# You can have variables in the URI, here's an example
		# self.post('/board/<element_id:int>/', callback=self.post_board) where post_board takes an argument (integer) called element_id


	def do_parallel_task(self, method, args=None):
		# create a thread running a new task
		# Usage example: self.do_parallel_task(self.contact_another_server, args=("10.1.0.2", "/index", "POST", params_dict))
		# this would start a thread sending a post request to server 10.1.0.2 with URI /index and with params params_dict
		thread = Thread(target=method,
						args=args)
		thread.daemon = True
		thread.start()


	def do_parallel_task_after_delay(self, delay, method, args=None):
		# create a thread, and run a task after a specified delay
		# Usage example: self.do_parallel_task_after_delay(10, self.start_election, args=(,))
		# this would start a thread starting an election after 10 seconds
		thread = Thread(target=self._wrapper_delay_and_execute,
						args=(delay, method, args))
		thread.daemon = True
		thread.start()


	def _wrapper_delay_and_execute(self, delay, method, args):
		time.sleep(delay) # in sec
		method(*args)


	def contact_another_server(self, srv_ip, URI, req='POST', params_dict=None):
		# Try to contact another serverthrough a POST or GET
		# usage: server.contact_another_server("10.1.1.1", "/index", "POST", params_dict)
		success = False
		try:
			if 'POST' in req:
				res = requests.post('http://{}{}'.format(srv_ip, URI),
									data=params_dict)
			elif 'GET' in req:
				res = requests.get('http://{}{}'.format(srv_ip, "/result"))
			# result can be accessed res.json()
			if res.status_code == 200:
				success = True
		except Exception as e:
			print("[ERROR] "+str(e))

		return success


	def propagate_to_all_servers(self, URI, req='POST', params_dict=None):
		for srv_ip in self.servers_list:
			if srv_ip != self.ip: # don't propagate to yourself
				success = self.contact_another_server(srv_ip, URI, req, params_dict)
				if not success:
					print("[WARNING ]Could not contact server {}".format(srv_ip))


	# route to ('/')
	def index(self):
		# we must transform the blackboard as a dict for compatiobility reasons
		
		#self.board["Majority"] =  self.majority_vector()
		return template('server/templates/index.tpl',
						board_title='Server {} ({})'.format(self.id,
															self.ip),
						board_dict=self.board.iteritems(),
						members_name_string='INPUT YOUR NAME HERE')

	# get on ('/board')
	def show_result(self):
		# we must transform the blackboard as a dict for compatibility reasons

		#print "Results From First Round: \n", self.votes
		#print "Results From Second Round: \n",self.generals

		self.board = dict()
		
		for key,value in self.votes.items():
			self.board[str(key)] =  self.votes[key]

		
		self.board["Majority"] =  self.majority_vector()

		return template('server/templates/vote_result_template.tpl',
						board_title='Server {} ({})'.format(self.id,
															self.ip),
						board_dict=self.board.iteritems())



	# post on ('/')
	def post_index(self):
		try:
			# we read the POST form, and check for an element called 'entry'
			new_entry = request.forms.get('entry')
			print("Received: {}".format(new_entry))
		except Exception as e:
			print("[ERROR] "+str(e))


	def get_template(self, filename):
		return static_file(filename, root='./server/templates/')

	# post on ('/attack')
	def vote_attack(self):
		try:
			self.my_vote = 'Attack'
			self.votes[self.id] = self.my_vote
			params = {
       			"value": self.my_vote,
            	"ip" : self.id
            }
			self.do_parallel_task(self.propagate_to_all_servers, args=('/propagate', "POST", params))
		except Exception as e:
			print("[ERROR] "+str(e))

	# post on ('/retreat')
	def vote_retreat(self):
		try:
			self.my_vote = 'Retreat'
			self.votes[self.id] = self.my_vote
			params = {
       			"value": self.my_vote,
            	"ip" : self.id
            }
			self.do_parallel_task(self.propagate_to_all_servers, args=('/propagate', "POST", params))

		except Exception as e:
			print("[ERROR] "+str(e))

	# post on ('/byzantine')
	def vote_byzantine(self):
		try:
			self.byzantine = True
			self.byzantine_member = self.byzantine_member + 1
			self.loyal_members = self.loyal_members - self.byzantine_member
			attack = 0
			retreat = 0
			# Check all the incoming votes if it can be made a tie
			for i in range(1, self.total_members+1):
				if i == self.id:
					continue
				value = self.votes[i]
				if value == self.mode[0]:
					attack+=1
				elif value == self.mode[1]:
					retreat+=1

			if(self.total_members == 4):
				cond1 = attack == 2 and retreat == 1 # two possible conditions where it can tie in a server of 4
				cond2 = attack == 1 and retreat == 2
				if cond1:
					self.votes_tied = True
					self.votes[self.id] = 'Retreat'
					params = {
						"value": 'Retreat',
						"ip" : self.id
					}
					self.do_parallel_task(self.propagate_to_all_servers, args=('/propagate', "POST", params))
					self.transmitted = True
					self.byzantine_agreement()
				elif cond2:
					self.votes_tied = True
					self.votes[self.id] = 'Attack'
					params = {
						"value": 'Attack',
						"ip" : self.id
					}
					self.do_parallel_task(self.propagate_to_all_servers, args=('/propagate', "POST", params))
					self.transmitted = True
					self.byzantine_agreement()
				else:
					# If cannot tie the votes, then send [True, False,......]
					self.byzantine_behavior_vote1()
		except Exception as e:
			print("[ERROR] "+str(e))

	# post on ('/propagate')
	def propagate_votes(self):
		try:
			value = request.forms.get('value')
			owner_id = request.forms.get('owner_id')
			ip = request.forms.get('ip')
			tie_breaker = bool(request.forms.get('tie_breaker'))
			self.votes[int(ip)] = value
			if (len(self.votes) == self.total_members) and ( not self.transmitted) :
				self.byzantine_agreement()
			if (tie_breaker == True and self.byzantine == True):
				print("swing votes: ")
				self.swing_votes();
		except Exception as e:
			print("[ERROR propagate_votes] "+str(e))


	def byzantine_agreement(self):
		try:
			attack = 0
			retreat = 0
			self.votes_tied = False
			# Check all the incoming votes if it can be made a tie
			for i in range(1, self.total_members+1):
				value = self.votes[i]
				if value == self.mode[0]:
					attack+=1
				elif value == self.mode[1]:
					retreat+=1
			if attack == retreat:
				self.votes_tied = True
			
			if self.votes_tied == True:
   				if self.id == 1:
					time.sleep(3)
					self.tie_breaker()
				else:
					pass
			else:
				self.transmitted = True
				self.exchange_vector()

		except Exception as e:
			print("[ERROR byzantine_agreement] "+str(e))

	def swing_votes(self):
		time.sleep(3)
		result = compute_byzantine_vote_round2(self.loyal_members,self.total_members,self.votes_tied)
		print("Inside swing votes")
		for i in range(0, len(result)):
			send_vector = ""
			for j in range(0, len(result)):
				send_vector = send_vector + "-" +str(j+1) + ":" + str(result[i][j])

			params= {"value": send_vector, "ip": i+1, "owner_id": self.id}
			# print("params before send: ", params)
			if (i+1 != self.id):
				address = "10.1.0.%s" % str(i+1)
				print("address: ", address, " params: ", params)
				self.do_parallel_task(self.contact_another_server, args=( address , '/exchange', 'POST', params))

 
 	def tie_breaker(self):
		try:
			if self.byzantine == True:
				self.byzantine_behavior_vote1()
			else:
				if self.my_vote == self.mode[0]:
					self.my_vote = "Retreat"
					self.votes[self.id] = self.my_vote
					params = {
						"value": self.my_vote,
						"ip" : self.id,
						"owner_id" : self.id,
						"tie_breaker" : True
					}
					self.votes_tied = False
					for i in range(1,self.total_members+1):
						if (i != self.id and not(self.byzantine)):
							address = "10.1.0.%s" % str(i)
							self.do_parallel_task(self.contact_another_server, args=( address , '/propagate', 'POST', params))

				else:
					self.my_vote = "Attack"
					self.votes[self.id] = self.my_vote
					params = {
						"value": self.my_vote,
						"ip" : self.id,
						"owner_id" : self.id,
						"tie_breaker" : True
					}
					self.votes_tied = False     
					for i in range(1,self.total_members+1):
						if (i != self.id and not(self.byzantine)):
							address = "10.1.0.%s" % str(i)
							self.do_parallel_task(self.contact_another_server, args=( address , '/propagate', 'POST', params))
			self.exchange_vector()
		except Exception as e:
			print("[ERROR tie_breaker] "+str(e))
   

	# post on ('/exchange')
	def exchange_votes(self):
		try:
			value = request.forms.get('value')
			owner_id = request.forms.get('owner_id')
			ip = request.forms.get('ip')
			result = value.split("-")
			result.pop(0)
			# print("checking, value: ", value, " ownerId: ", owner_id, " ip: ", ip)
			if len(self.generals) == 0:
				self.create_dictionay(self.total_members)
				self.generals[self.id] = self.votes
			for i in result:
				j = i.split(":")
				self.generals[int(owner_id)][int(j[0])] = j[1]

  			print("Vectors exchange finished, check results!!", self.generals)

		except Exception as e:
			print("[ERROR in exchange_votes] "+str(e))


	def create_dictionay(self,total):

		self.generals =  {i: dict(zip(range(1,int(total)),"")) for i in range(1,int(total)+1)}

	def exchange_vector(self):
		print("Exchange vector called")
		time.sleep(2)
		result = ""
		for key,value in self.votes.items():
			result = result + "-" +str(key) + ":" + value
			# result[key] = value
		params = {"value" : result, "ip" : key, "owner_id": self.id}
		
		self.do_parallel_task(self.propagate_to_all_servers, args=( "/exchange", "POST", params))

	def majority_vector(self):
		attack = 0
		retreat = 0
		result_vector = []


		if len(self.votes) == len(self.servers_list):

			for i in range(1,len(self.votes)+1):
				for j in range(1,len(self.votes)+1):
					# print("self.generals at i,j: ", self.generals[i][j])
					if self.generals[i][j] == self.mode[0]:
						
						attack = attack + 1

					else:

						retreat = retreat + 1

				if attack>=(len(self.votes)/2):

					result_vector.append(self.mode[0])

				elif retreat>=(len(self.votes)/2):

					result_vector.append(self.mode[1])

				else:
					result_vector.append(self.mode[2])

				attack = 0
				retreat = 0

			print "vector", result_vector
			print "value", self.majority_element(result_vector)

		return self.majority_element(result_vector)

	def majority_element(self,result_vector):

		attack = 0
		retreat = 0

		for i in result_vector:
			if i == self.mode[0]:
				attack+=1
			elif i == self.mode[1]:
				retreat+=1


		if attack >= retreat:
			return self.mode[0]
		else:
			return self.mode[1]

	def byzantine_behavior_vote1(self):
		self.votes[self.id] = 'True'
		result = compute_byzantine_vote_round1(self.loyal_members,self.total_members,self.votes_tied)
		self.votes_tied = False
		for i in range(1,self.total_members+1):
			if (i != self.id and not(str(i) in self.byzantine_list)):

				params = {"value" : result[0], "owner_id" : self.id,  "ip" : self.id, "tie_breaker" : True}
				address = "10.1.0.%s" % str(i)
				print("address: ", address, " params: ", params)
				self.do_parallel_task(self.contact_another_server, args=( address , '/propagate', 'POST', params))
				result.pop(0)


	def byzantine_algorithm(self,loyal_members,byzantine_member,total_members):
		print("Run byzantine algorithm, come over failed nodes")
		result = compute_byzantine_vote_round1(loyal_members,total_members,True)
		print("byzantine_vote_round_1: ", result)
		for i in range(1,total_members+1):
			if (i != self.id and not(str(i) in self.byzantine_list)):

				data = {"value" : result[0], "owner_id" : self.id,  "ip" : self.id}
				address = "10.1.0.%s" % str(i)

				# self.contact_another_server( address , '/propagate', 'POST', data)

				result.pop(0)
		print("after running algo, the result is: ", result)
		for i in self.byzantine_list:
			self.votes[int(i)] = self.mode[2]		
			for j in range(1,total_members+1):
				self.generals[int(i)][j]  = self.mode[2]  	

		result = compute_byzantine_vote_round2(loyal_members,total_members,True)
		print("What is this result", result)
		c = ""
		for i in range(0,loyal_members):
			for j in range(0,total_members):
				c = c+"-"+str(j+1)+":"+str(result[i][j])
			if (i+1 != self.id ):
				data = {"value": c, "ip": "", "owner_id" : self.id}
				# self.contact_another_server( "10.1.0.%s" % str(i+1) , '/exchange', 'POST', data)
		print("What's in c: ", c)


# ------------------------------------------------------------------------------------------------------
def main():
	PORT = 80
	parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
	parser.add_argument('--id',
						nargs='?',
						dest='id',
						default=1,
						type=int,
						help='This server ID')
	parser.add_argument('--servers',
						nargs='?',
						dest='srv_list',
						default="10.1.0.1,10.1.0.2",
						help='List of all servers present in the network')
	args = parser.parse_args()
	server_id = args.id
	server_ip = "10.1.0.{}".format(server_id)
	servers_list = args.srv_list.split(",")

	try:
		server = Server(server_id,
						server_ip,
						servers_list)
		bottle.run(server,
				   host=server_ip,
				   port=PORT)
	except Exception as e:
		print("[ERROR] "+str(e))


# ------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
	main()
