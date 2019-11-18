from bottle import route, run, template, get, post, request

@route('/')
@route('/hello/<name>')
def greet(name='Stranger'):
    return template('Hello {{name}}, how are you?', name=name)

@get('/input') 
def input():
    return '''
        <form action="/input" method="post" id="usrform">
            <b>Name:</b> <input name="username" type="text" />
            <input value="Submit" type="submit" />
        </form>
        <br>
        <b>About You:</b>
        <br>
        <textarea rows="4" cols="50" name="description" form="usrform">Write something about yourself...</textarea>
    '''
def check_empty(name, description):
    if (len(name) >0) & (len(description) > 0):
        return True
    else:
        return False

@post('/input') 
def do_input():
    name = request.forms.get('username')
    name = name.upper()
    description = request.forms.get('description')
    if check_empty(name, description):
        return "<h2>Here's something about " + name + ":</h2>" + "<p>" + description + "</p>"
    else:
        return "<h1>Don't be shy to write about yourself.</h1>"

run(host='localhost', port=8080, debug=True)