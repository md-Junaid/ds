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


# ------------------------------------------------------------------------------------------------------
class Server(Bottle):

    def __init__(self, ID, IP, servers_list):
        super(Server, self).__init__()
        self.blackboard = Blackboard()
        self.id = int(ID)
        self.ip = str(IP)
        self.servers_list = servers_list
        self.l_clock = 0
        self.global_clock = []
        self.msg_timer_start = 0
        self.msg_timer_end = 0
        # list all REST URIs
        # if you add new URIs to the server, you need to add them here
        self.route('/', callback=self.index)
        self.get('/board', callback=self.get_board)
        self.post('/', callback=self.post_index)
        self.post('/board', callback=self.post_board)
        self.post('/board/<element_id:int>/', callback=self.handle_req)
        self.post('/propagate', callback=self.propagate)
        self.post('/gclock', callback=self.update_global_clock)
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
                res = requests.get('http://{}{}'.format(srv_ip, URI))
            # result can be accessed res.json()
            if res.status_code == 200:
                success = True
        except Exception as e:
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
        # we must transform the blackboard as a dict for compatiobility reasons
        board = dict()
        board = self.blackboard.get_content()
        return template('server/templates/index.tpl',
                        board_title='Server {} ({}) LC({})'.format(self.id,
                                                            self.ip, self.l_clock),
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


    # propagate add on all servers (other boards)
    def post_index(self):
        try:
            self.msg_timer_start = time.time()
            # we read the POST form, and check for an element called 'entry'
            new_entry = request.forms.get('entry')
            t_stamp = int(request.forms.get('t_stamp'))
            srv_id = int(request.forms.get('srv_id'))
            lc_tup = [t_stamp, srv_id]
            self.global_clock.append(lc_tup)
            self.msg_timer_end = time.time()
            self.l_clock = max(self.l_clock, t_stamp)
            self.l_clock = self.l_clock + 1
            lc_tup = [self.l_clock, self.id]
            self.global_clock.append(lc_tup)
            self.blackboard.set_content(new_entry)
            payload_clock = {
                't_stamp': self.l_clock,
                'srv_id': self.id
            }
            self.propagate_to_all_servers('/gclock', 'POST', payload_clock)
            total = self.msg_timer_end - self.msg_timer_start
            # print("My logical clocks are: ", self.global_clock)
            print("Max Time for a msg to reach other server: ", total)
        except Exception as e:
            print("[ERROR] "+str(e))
    
    # post on ('/board') (my board)
    def post_board(self):
        try:
            self.msg_timer_start = time.time()
            # we read the POST form, and check for an element called 'entry'
            new_entry = request.params.get('entry')
            self.l_clock = self.l_clock + 1
            self.blackboard.set_content(new_entry)
            self.msg_timer_end = time.time()
            payload = {
                'entry' : new_entry,
                't_stamp' : self.l_clock,
                'srv_id' : self.id
            }
            lc_tup = [self.l_clock, self.id]
            self.global_clock.append(lc_tup)
            self.propagate_to_all_servers('/', 'POST', payload)
            total = self.msg_timer_end - self.msg_timer_start
            print("Time to send msg on my own board: ", total)
        except Exception as e:
            print("[ERROR] "+str(e))
        
    # delete or modify item on my board
    def handle_req(self, element_id):
        self.msg_timer_start = time.time()
        option = request.forms.get('delete')
        modified_val = request.forms.get('entry')
        self.l_clock = self.l_clock + 1
        if option == '1':
            self.blackboard.delete_item(element_id)
        else:
            self.blackboard.modify_item(element_id, modified_val)
        lc_tup = [self.l_clock, self.id]
        self.global_clock.append(lc_tup)
        self.msg_timer_end = time.time()
        payload = {
            'option': option,
            'id': element_id,
            'entry': modified_val,
            't_stamp' : self.l_clock,
            'srv_id' : self.id
        }
        self.propagate_to_all_servers('/propagate', 'POST', payload)
        total = self.msg_timer_end - self.msg_timer_start
        print("Time to send msg on my own board: ", total)
        return 'ok'
    
    # Propagating deleted or modified item to all servers (on other boards)
    def propagate(self):
        self.msg_timer_start = time.time()
        option = request.forms.get('option')
        modified_val = request.forms.get('entry')
        elem_id = int(request.forms.get('id'))
        t_stamp = int(request.forms.get('t_stamp'))
        srv_id = int(request.forms.get('srv_id'))
        lc_tup = [t_stamp, srv_id]
        self.global_clock.append(lc_tup)
        if option == '1':
            self.blackboard.delete_item(elem_id)
        else:
            self.blackboard.modify_item(elem_id, modified_val)
        self.msg_timer_end = time.time()
        self.l_clock = max(self.l_clock, t_stamp)
        self.l_clock = self.l_clock + 1
        lc_tup = [self.l_clock, self.id]
        self.global_clock.append(lc_tup)
        payload_clock = {
            't_stamp': self.l_clock,
            'srv_id': self.id
        }
        self.propagate_to_all_servers('/gclock', 'POST', payload_clock)
        total = self.msg_timer_end - self.msg_timer_start
        print("Max Time for a msg to reach other server: ", total)
        return 'ok'
    
    # Maintain global logical clock 
    def update_global_clock(self):
        l_clock = int(request.forms.get('t_stamp'))
        srv_id = int(request.forms.get('srv_id'))
        for p in self.global_clock:
            # if concurrent calls then check this condition and arrange with lower ip first
            if p[0] == l_clock and srv_id < p[1]:
                temp_id = p[1]
                p[1] = srv_id
                srv_id = temp_id
                lc_tup = [l_clock, srv_id]
            else:
                lc_tup = [l_clock, srv_id]
        self.global_clock.append(lc_tup)
        print("global clock list: ", self.global_clock)
            
    def get_template(self, filename):
        return static_file(filename, root='./server/templates/')
        

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
