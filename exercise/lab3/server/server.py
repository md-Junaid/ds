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
        # list all REST URIs
        # if you add new URIs to the server, you need to add them here
        self.route('/', callback=self.index)
        self.get('/board', callback=self.get_board)
        self.post('/', callback=self.post_index)
        self.post('/board', callback=self.post_board)
        self.post('/board/<element_id:int>/', callback=self.handle_req)
        self.post('/propagate', callback=self.propagate)
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
                        board_title='Server {} ({}) T{}({})'.format(self.id,
                                                            self.ip, self.id, self.l_clock),
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
            clock = int(request.forms.get('clock'))
            self.l_clock = clock + 1
            self.blackboard.set_content(new_entry)
        except Exception as e:
            print("[ERROR] "+str(e))
    
    # post on ('/board')
    def post_board(self):
        try:
            # we read the POST form, and check for an element called 'entry'
            new_entry = request.params.get('entry')
            self.blackboard.set_content(new_entry)
            self.l_clock = self.l_clock + 1
            payload = {
                'entry' : new_entry,
                'clock' : self.l_clock
            }
            self.propagate_to_all_servers('/', 'POST', payload)
        except Exception as e:
            print("[ERROR] "+str(e))
        
    # delete or modify item
    def handle_req(self, element_id):
        option = request.forms.get('delete')
        modified_val = request.forms.get('entry')
        self.l_clock = self.l_clock + 1
        if option == '1':
            self.blackboard.delete_item(element_id)
        else:
            self.blackboard.modify_item(element_id, modified_val)
        payload = {
            'option': option,
            'id': element_id,
            'entry': modified_val,
            'clock' : self.l_clock
        }
        self.propagate_to_all_servers('/propagate', 'POST', payload)
        return 'ok'
    
    # Propagating deleted or modified item to all servers
    def propagate(self):
        option = request.forms.get('option')
        modified_val = request.forms.get('entry')
        elem_id = int(request.forms.get('id'))
        clock = int(request.forms.get('clock'))
        self.l_clock = clock + 1
        if option == '1':
            self.blackboard.delete_item(elem_id)
        else:
            self.blackboard.modify_item(elem_id, modified_val)
        return 'ok'
            
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
