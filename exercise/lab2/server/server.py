# coding=utf-8
import argparse
import json
import sys
from threading import Lock, Thread
import time
import traceback
import bottle
from bottle import Bottle, request, template, run, static_file, abort
import requests
from concurrent.futures import ThreadPoolExecutor, wait
from enum import Enum
# ------------------------------------------------------------------------------------------------------

class Blackboard():

    def __init__(self):
        self.content = dict()
        self.ID = 0
        self.lock = Lock() # use lock when you modify the content


    def get_content(self):
        with self.lock:
            cnt = self.content
        return cnt


    def set_content(self, new_content):
        with self.lock:
            self.ID = self.ID + 1
            self.content[self.ID] = new_content
        return
    
    def delete_item(self, id):
        with self.lock:
            self.content.pop(id)
        return
    
    def modify_item(self, id, val):
        with self.lock:
            self.content[id] = val
        return

class state(Enum):
    ELECTION_MODE = 1
    SERVING_MODE = 2
    HANDLING_REQ = 3

# ------------------------------------------------------------------------------------------------------
class Server(Bottle):

    def __init__(self, ID, IP, servers_list):
        super(Server, self).__init__()
        self.blackboard = Blackboard()
        self.id = int(ID)
        self.ip = str(IP)
        self.servers_list = servers_list
        self.slave = False
        self.leader_server = ''
        self.stop_multiple_calls = 0
        self.srvs_down = []
        self.stop_multiple_calls_contact = 0
        self.server_state = None
        self.election_start = 0
        self.election_end = 0
        # list all REST URIs
        # if you add new URIs to the server, you need to add them here
        self.route('/', callback=self.index)        
        self.get('/board', callback=self.get_board)
        self.post('/', callback=self.post_index)
        self.post('/board', callback=self.post_board)
        self.post('/board/<element_id:int>/', callback=self.handle_req)
        self.post('/propagate', callback=self.propagate)
        self.post('/server_ctrl', callback=self.post_server_ctrl)
        # we give access to the templates elements
        self.get('/templates/<filename:path>', callback=self.get_template)
        # You can have variables in the URI, here's an example
        # self.post('/board/<element_id:int>/', callback=self.post_board) where post_board takes an argument (integer) called element_id
        
        # start election as severs are up
        self.pool = ThreadPoolExecutor(max_workers=20)
        self.pool.submit(self.start_election, 20)


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
        msg_type = params_dict.get('type')
        # print("Contacting other server which  is: ", srv_ip, " initiated by: ", params_dict)
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(srv_ip, URI),
                                    data=params_dict)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(srv_ip, URI))
            # result can be accessed res.json()
            if res.status_code == 200:
                success = True
        except Exception as e:
            if (msg_type == 'start election'):
                print("msg type from contact another: ", msg_type)
                self.contact_failed(srv_ip, params_dict)
            print("[ERROR] "+str(e))
        return success


    def propagate_to_all_servers(self, URI, req='POST', params_dict=None):
        for srv_ip in self.servers_list:
            if srv_ip != self.ip: # don't propagate to yourself
                success = self.do_parallel_task(self.contact_another_server, args=(srv_ip, URI, req, params_dict))
                if not success:
                    print("[WARNING ]Could not contact server {}".format(srv_ip))
                
                    


    # route to ('/')
    def index(self):
        # Displaying the server role on UI
        if (self.slave == True):
            self.display_my_role = 'slave'
        else:
            self.display_my_role = 'leader'
            
        # Displaying Election attribute on UI
        if (self.server_state == state.ELECTION_MODE):
            self.election_attr = 'Under Election'
        elif (self.server_state == state.SERVING_MODE):
            self.election_attr = 'Serving mode'
        elif (self.server_state == state.HANDLING_REQ):
            self.election_attr = 'Handling Requests'
        # we must transform the blackboard as a dict for compatiobility reasons
        board = dict()
        board = self.blackboard.get_content()
        return template('server/templates/index.tpl',
                        board_title='Server {} ({}) ({}) ({})'.format(self.id,
                                                            self.ip, self.election_attr, self.display_my_role),
                        board_dict=board.iteritems(),
                        members_name_string='ERMIRA, JUNAID')

    # get on ('/board')
    def get_board(self):
        # we must transform the blackboard as a dict for compatibility reasons
        board = dict()
        board = self.blackboard.get_content()
        return template('server/templates/blackboard.tpl',
                        board_title='Server {} ({})'.format(self.id,
                                                            self.ip),
                        board_dict=board.iteritems())


    # propagate add on all servers 
    def post_index(self):
        try:
            # we read the POST form, and check for an element called 'entry'
            new_entry = request.forms.get('entry')
            self.blackboard.set_content(new_entry)
        except Exception as e:
            print("[ERROR] "+str(e))
    
    # post on ('/board')
    def post_board(self):
        try:
            if (self.server_state == state.ELECTION_MODE):
                return
            else:
                # we read the POST form, and check for an element called 'entry'
                new_entry = request.params.get('entry')
                payload = {
                    'entry' : new_entry
                }
                if(self.ip == self.leader_server):
                    self.blackboard.set_content(new_entry)
                    self.propagate_to_all_servers('/', 'POST', payload)
                else:
                    self.contact_another_server(self.leader_server, '/board', 'POST', payload )
        except Exception as e:
            print("[ERROR] "+str(e))
       
            
    # delete or modify item
    def handle_req(self, element_id):
        try:
            if (self.server_state == state.ELECTION_MODE):
                return 'ok'
            elif (self.server_state == state.HANDLING_REQ):
                abort(401, "Resource in user, please try again later")
                return 'ok'
            elif (self.server_state == state.SERVING_MODE):
                option = request.forms.get('delete')
                modified_val = request.forms.get('entry')
                payload = {
                        'delete': option,
                        'id': element_id,
                        'entry': modified_val
                    }
                
                if( self.ip == self.leader_server):
                    self.server_state = state.HANDLING_REQ
                    # time.sleep(10)
                    if option == '1':
                        self.blackboard.delete_item(element_id)
                    else:
                        self.blackboard.modify_item(element_id, modified_val)
                    self.propagate_to_all_servers('/propagate', 'POST', payload)
                    self.server_state = state.SERVING_MODE
                else:
                    self.contact_another_server(self.leader_server, '/board/{0}/'.format(element_id), 'POST', payload )
        except Exception as e:
            print("[ERROR] "+str(e))
    
    # Propagating deleted or modified item to all servers
    def propagate(self):
        option = request.forms.get('delete')
        modified_val = request.forms.get('entry')
        elem_id = int(request.forms.get('id'))
        if option == '1':
            self.blackboard.delete_item(elem_id)
        else:
            self.blackboard.modify_item(elem_id, modified_val)
        return 'ok'
            
    def get_template(self, filename):
        return static_file(filename, root='./server/templates/')
    
    # ------------------------------ LAB 2 ---------------------------------------------------
    
    # First election call, send start election message to next 2 higher ips
    def start_election(self, args=None):
        if (args):
            time.sleep(args)
        self.server_state = state.ELECTION_MODE
        success = self.send_election_msg()
        self.election_start = time.time()
        return True
    
    def send_election_msg(self):
        count = 0
        self.stop_multiple_calls_contact = 0
        servers_to_skip = len(self.srvs_down)
        next_2_servers = len(self.srvs_down)
        payload = {
            'type': 'start election',
            'source_ip': self.ip
        }
        for x in self.servers_list:
            if (self.ip < x):
                count = count + 1
                if (servers_to_skip):
                    servers_to_skip = servers_to_skip - 1
                    continue
                self.do_parallel_task(self.contact_another_server, args=(x, '/server_ctrl', 'POST', payload))
                if (count == (2 + next_2_servers)):
                    break
        return True
            
    def contact_failed(self, srv_ip, params_dict):
        if (self.slave == True):
            print("I'm slave now, so I dont send election msg")
            return
        msg_type = params_dict.get('type')
        self.srvs_down.append(srv_ip)
        print("Call only for start election msg: ", msg_type)
        self.stop_multiple_calls_contact = self.stop_multiple_calls_contact + 1
        if (self.stop_multiple_calls_contact == 2):
            self.send_election_msg()
        return 'ok'
            
    
    # Handling election messages on each server
    def post_server_ctrl(self):
        if (self.server_state == state.SERVING_MODE):
            pass
        else:
            msg_type = request.forms.get('type')
            source_ip = request.forms.get('source_ip')
            if (msg_type == 'start election'):
                answer = {
                    'type': 'alive'
                }
                self.do_parallel_task(self.contact_another_server, args=(source_ip, '/server_ctrl', 'POST', answer))                
                payload = {
                    'type': msg_type,
                    'source_ip': self.ip
                }
                self.pool.submit(self.declare_me_leader)
            elif (msg_type == 'alive'):
                self.slave = True
                self.stop_multiple_calls = self.stop_multiple_calls + 1
                if self.stop_multiple_calls < 2:
                    self.pool.submit(self.check_leader_up)
            elif (msg_type == 'victory'):
                self.leader_server = source_ip
                self.server_state = state.SERVING_MODE
                self.election_end = time.time()
                total = self.election_end - self.election_start
                print('\nTime to complete election: ', total)
                print('Selected leader is: ', self.leader_server)
                return 'success'    
    
    # This function waits for 5 secs and then check if higher ip is not slave
    def declare_me_leader(self):
        if (len(self.servers_list) < 10):
            time.sleep(5)
        elif (len(self.servers_list) < 20):
            time.sleep(10)
        if(self.slave == False):
            self.stop_multiple_calls = self.stop_multiple_calls + 1
            if self.stop_multiple_calls < 2:
                payload = {
                    'type': 'victory',
                    'source_ip': self.ip
                }
                self.server_state = state.SERVING_MODE
                for srv_ip in self.servers_list:
                    if (srv_ip != self.ip): # don't propagate to yourself
                        self.do_parallel_task(self.contact_another_server, args=(srv_ip, '/server_ctrl', 'POST', payload))
                self.leader_server = self.ip
                self.election_end = time.time()
                total = self.election_end - self.election_start            
                print('\nTime to complete election: ', total)
        return 'ok'
    
    # This function checks if there is a leader
    # if a leader exists then check if responding
    # if not responging call new election 
    def check_leader_up(self):
        time.sleep(10)
        if (self.leader_server == ''):
            servers_count = len(self.servers_list)
            if (self.servers_list[servers_count-1] == self.my_next_2.keys()[0]):
                self.slave = False
                self.declare_me_leader()
                
        else:
            print("Our leader is: ", self.leader_server)

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
