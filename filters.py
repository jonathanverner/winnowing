import parser,symbol,token
class PythonTransform(object):
  def __init__(self):
    self.names = {}
    self.next_name=0
    self.mangle_names = False
    self.discard_strings = False
    self.tokNM={}
    last_tok=0
    for (k,v) in token.tok_name.items():
      self.tokNM[k] = chr(last_tok)
      last_tok +=1

  def parse(self,code,mangle_names = True,discard_strings = False):
    try:
      st = parser.suite(code)
    except Exception,e:
      print "WARNING: ", e
      return code
    self.token_stream = []
    self.mangle_names = mangle_names
    self.discard_strings = discard_strings
    self._token_stream(st.tolist())
    return ','.join(self.token_stream)

  def _token_stream(self,ast):
    showNext = False
    nameToken = False
    for node in ast:
      if type(node) == list:
        self._token_stream(node)
      else:
        if node in token.tok_name:
          showNext = True

          if token.tok_name[node] == 'NAME':
            nameToken = True
          elif token.tok_name[node] == 'STRING' and self.discard_strings:
            showNext = False
          elif token.tok_name[node] == 'NEWLINE':
            showNext = False
            continue
          self.token_stream.append(self.tokNM[node])
        elif showNext:
          if self.mangle_names and nameToken:
            if not node in self.names:
              self.names[node] = str(self.next_name)
              self.next_name +=1
            self.token_stream.append(self.names[node])
            nameToken = False
          else:
            self.token_stream.append(node)
          showNext = False

def python_filter_mangle(code):
  tr = PythonTransform()
  return tr.parse(ascii(code),mangle_names = True)

def python_filter_mangle_discardstring(code):
  tr = PythonTransform()
  return tr.parse(ascii(code),mangle_names = True, discard_strings = True)

def python_filter(code):
  tr = PythonTransform()
  return tr.parse(ascii(code),mangle_names = False)

def noop_filter(code):
  return code

def ascii(code):
  return unicode(code,encoding='ascii',errors='ignore')

filters = {
  'python_mangle_discardstr':python_filter_mangle_discardstring,
  'python_mangle':python_filter_mangle,
  'python':python_filter,
  'noop':noop_filter,
  'ascii':ascii,
}
