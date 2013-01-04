#!/usr/bin/python
import json
import gzip
import argparse
import os
import filters

# See also http://arxiv.org/abs/0705.4676
# http://www.cparity.com/projects/AcmClassification/samples/256168.pdf
# http://code.google.com/p/ngramhashing/
class Hasher(object):
  def __init__(self,initial):
    # http://www.ams.org/journals/mcom/1999-68-225/S0025-5718-99-00996-5/S0025-5718-99-00996-5.pdf
    self.a=276137484736346373
    self.m=2**60
    self.h = self.fullHash(initial)
    self.window=map(lambda x:ord(x),initial)
    self.length = len(initial)

  def fullHash(self,string):
    h = 0
    for c in string:
      h *= self.a
      h += ord(c)
      h = int(h % self.m)
    return h

  def update(self,char):
    self.h = int(((self.h - self.window[0]*(self.a**(self.length-1)))*self.a+ord(char))%self.m)
    del self.window[0]
    self.window.append(ord(char))
    return self.h


def minPos( lst ):
  m = lst[0]
  p = 0
  for i in range(1,len(lst)):
    if lst[i] < m:
      m = lst[i]
      p = i
  return (m,p)

def global_pos( wpos, window_len, window_pos ):
  return window_pos-window_len+wpos+1

# http://theory.stanford.edu/~aiken/publications/papers/sigmod03.pdf
def finger_print(text, hash_len, window_len ):
  # window --- contains the hashes from the current window
  window=[]

  # Initialize the Hasher
  H = Hasher( chr(0)+text[0:hash_len-1] )

  # Compute the hashes from the first window
  for i in range(window_len):
    window.append(H.update(text[i+hash_len-1]))

  # min_hash      --- contains the minimal hash of the current window
  # min_wpos      --- contains the position of the minimal hash in the current window
  min_hash,min_wpos = minPos(window)

  # pick --- contains the selected hashes together with their position in text
  pick = {min_hash:[min_wpos]}

  # Cycle through the windows, spos is the index of the last
  # hash of the current window in the text
  for window_start_pos in range(window_len,len(text)-(window_len+hash_len)):

    # Move the window one step to the right
    del window[0]
    window.append( H.update(text[window_start_pos+hash_len-1]) )

    # Update the position of the previously minimal hash in the current window
    min_wpos -= 1

    # If the previously minimal hash is still in the current window
    # the minimum of the current window may be computed just by comparing
    # the newly added hash with the previously minimal hash
    if min_wpos >= 0:
      if min_hash > window[-1]:
        min_hash = window[-1]
        min_wpos = window_len-1
        gpos = global_pos(min_wpos, window_len, window_start_pos )
        if min_hash in pick:
          pick[min_hash].append(gpos)
        else:
          pick[min_hash]=[gpos]
    # Otherwise we must scan the current window for the new minimum
    else:
      min_hash,min_wpos=minPos(window)
      gpos = global_pos(min_wpos, window_len, window_start_pos )
      if min_hash in pick:
        pick[min_hash].append(gpos)
      else:
        pick[min_hash] = [gpos]
  return pick


class DocumentDB(object):
  def __init__(self, hash_len=50, window_len=50, default_filter='ascii' ):
    self.hl = hash_len
    self.wl = window_len
    self.fp_locations = {}
    self.docs = {}
    self.default_filter = default_filter

  def add_document(self, docName, docText, filter = None ):
    if filter is None:
      filter = self.default_filter
    fp = finger_print( filters.filters[filter](docText), self.hl, self.wl)
    self.docs[docName]=unicode(docText,encoding='utf-8',errors='ignore')
    for (h,pos_list) in fp.items():
      if not str(h) in self.fp_locations:
        self.fp_locations[str(h)]=[]
      for p in pos_list:
        self.fp_locations[str(h)].append(docName+':'+str(p))

  def find_duplicates(self):
    for doc in self.docs.keys():
      pass


  def doc_snippet(self, docName, docPos, context):
    return self.docs[docName][docPos-context:docPos+context]

  def match_document(self, docText, num_matches = 20, filter = None):
    if filter is None:
      filter = self.default_filter
    fp = finger_print( filters.filters[filter](docText), self.hl, self.wl )
    docMatches={}
    for (h,pos) in fp.items():
      h = str(h)
      if h in self.fp_locations:
        for locs in self.fp_locations[h]:
          docName, docPos = locs.split(':')
          if docName in docMatches:
            docMatches[docName].append((docPos,pos))
          else:
            docMatches[docName]=[(docPos,pos)]
    ret = sorted(docMatches.items(),key=lambda x:len(x[1]),reverse=True)[0:num_matches]
    return (ret,len(fp))

  def save(self, fname):
    save_dict = {}
    save_dict['hash_len'] = self.hl
    save_dict['window_len'] = self.wl
    save_dict['finger_prints'] = self.fp_locations
    save_dict['documents'] = self.docs
    save_dict['default_filter'] = self.default_filter
    f = gzip.open(fname,mode='w')
    json.dump(save_dict, f, indent=2)
    f.close()

  def load(self, fname):
    f = gzip.open(fname,'r')
    load_dict = json.load(f)
    f.close()
    self.hl = load_dict['hash_len']
    self.wl=load_dict['window_len']
    self.fp_locations = load_dict['finger_prints']
    self.docs = load_dict['documents']
    self.default_filter = load_dict['default_filter']



def main():
  parser = argparse.ArgumentParser(description='A program to detect plagiarism')
  parser.add_argument('-db', '--database', help='document fingerprint database', default=os.environ['HOME']+'/.winnowing/fpdb.json.gz')

  subparsers = parser.add_subparsers(title='action', description='available actions', dest='action')

  # Statistics
  parser_stat = subparsers.add_parser('stat',help='print statistical info')

  # Transform
  parser_trans = subparsers.add_parser('trans',help='Just apply a filter to the file')
  parser_trans.add_argument("document",type=argparse.FileType('r'),help='filename of the document to transform')
  parser_trans.add_argument("--filter",help='filter to preprocess the documents with (list to print available filters)',choices=filters.filters.keys()+['list'])


  # Init the DB
  parser_init = subparsers.add_parser('init',help='initialize the database')
  parser_init.add_argument("--window_len",type=int,help='window length',default=50)
  parser_init.add_argument("--hash_len",type=int,help='hash length',default=50)
  parser_init.add_argument("--filter",help='filter to preprocess the documents with (list to print available filters)',choices=filters.filters.keys()+['list'])

  # Batch add documents to the DB
  parser_badd = subparsers.add_parser('add',help='add multiple documents to the database')
  parser_badd.add_argument('documents',type=argparse.FileType('r'),nargs='+',help='filenames of the documents to add')


  # Match a document against the DB
  parser_match = subparsers.add_parser('match', help='match a document against the database')
  parser_match.add_argument("document",type=argparse.FileType('r'),help='filename of the document to match')
  parser_match.add_argument("--treshold",type=int,help='percent of matched hashes to assume a match', default=10 )
  parser_match.add_argument("--min-matches", type=int,help='minimum number of matched fingerprints to assume a match', default=10)
  parser_match.add_argument("--number_of_matches", type=int,help='number of matching documents to print', default=5 )
  parser_match.add_argument("--context",type=int,help='number of characters of context to print with a match', default=40 )
  parser_match.add_argument("--only-names",action='store_true', help='only print names of matching documents + number of matches', default=False)
  parser_match.add_argument("--quiet",action='store_true',help='do not print anything, if match present exit with success, otherwise exit with failure',default=False)

  args = parser.parse_args()

  if args.action == 'init':
    if args.filter and args.filter == 'list':
      print 'Available filters:'
      print '  '+'\n  '.join(filters.filters.keys())
      exit(0)
    db = DocumentDB( args.hash_len, args.window_len, default_filter = args.filter )
    db.save(args.database)
    exit(0)
  elif args.action == 'trans':
    if args.filter and args.filter == 'list':
      print 'Available filters:'
      print '  '+'\n  '.join(filters.filters.keys())
      exit(0)
    print filters.filters[args.filter](args.document.read())


  try:
    os.stat(args.database)
    db = DocumentDB()
    db.load(args.database)
  except Exception as e:
    print "Error: database file '"+args.database+"' is corrupt or does not exist:"
    print " "*10, e
    exit(1)

  if args.action == 'add':
    for d in args.documents:
      print "Adding ", d.name, "...",
      try:
        db.add_document(d.name,d.read())
      except Exception, e:
        print "Fail (", e,")"
      print "OK"
    db.save(args.database)
  elif args.action =='match':
    try:
      matches,num_of_hashes=db.match_document(args.document.read(),num_matches=args.number_of_matches)
    except Exception, e:
      print "Error matching document (", e, ")"
      exit(2)
    one_percent = num_of_hashes/float(100)
    exit_status=1
    for (docName,positions) in matches:
      percent = int(len(positions)/one_percent)
      if docName == args.document.name or percent < args.treshold or len(positions) < args.min_matches:
        continue
      exit_status=0
      if args.quiet:
        break
      print "="*20, args.document.name, "="*20
      print "Document:", docName
      print "Matches:", len(positions), '(',percent, '%)'
      if not args.only_names:
        for p in positions:
          print "--- src:",p[0],'dst:',p[1],"---"
          print db.doc_snippet(docName,int(p[0]),args.context)
      print "="*50
    exit(exit_status)
  elif args.action == 'stat':
    print "Number of hashes:    ", len(db.fp_locations)
    print "Number of documents: ", len(db.docs)
    print "Size of documents:   ", sum(map(lambda x:len(x),db.docs.values()))/1024, "Kb"
    print "Default filter:      ", db.default_filter
    print "Window size:         ", db.wl
    print "Hash size:           ", db.hl

if __name__ == "__main__":
  main()










