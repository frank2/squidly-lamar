#!/usr/bin/env python

import os
import sys

class StateError(Exception):
   pass

class StateTerminate(StateError):
   pass

class StateMachine:
   def __init__(self, tape, init_state):
      self.tape = tape
      self.current_state = init_state

   def run(self):
      read = 0

      while 1:
         #print '[DEBUG] Entering state %s at tape index %d' % (repr(self.current_state), read)
         try:
            read = self.current_state(read)
         except StateTerminate:
            #print '[DEBUG] Hit StateTerminate.'
            break

class SSHPatternMachine(StateMachine):
   def __init__(self, pattern, match_against=None):
      self.match_against = match_against
      StateMachine.__init__(self, pattern, self.init_state)

   def init_state(self, tape_index):
      if not self.match_against:
         raise StateError("nothing to match against pattern %s" % self.tape)

      self.match_index = 0
      self.match_limit = len(self.match_against)

      self.pattern_pointer = -1
      self.match_pointer = -1

      self.current_state = self.static_state
      return tape_index

   def static_state(self, tape_index):
      if tape_index >= len(self.tape) or self.match_index >= self.match_limit:
         self.current_state = self.pattern_aware_state
         return tape_index

      pc = self.tape[tape_index]
      mc = self.match_against[self.match_index]

      if pc == '*':
         self.current_state = self.pattern_aware_state
         return tape_index

      if not mc == pc and not pc == '?':
         raise StateError("pattern does not match")

      self.match_index += 1
      return tape_index+1

   def pattern_aware_state(self, tape_index):
      if tape_index >= len(self.tape) or self.match_index >= self.match_limit:
         self.current_state = self.exhaust_pattern_state
         return tape_index

      pc = self.tape[tape_index]
      mc = self.match_against[self.match_index]

      if pc == '*':
         self.pattern_pointer = tape_index+1

         if self.pattern_pointer >= len(self.tape):
            raise StateTerminate

         self.match_pointer = self.match_index+1
         return self.pattern_pointer
      elif pc == mc or pc == '?':
         self.match_index += 1
         return tape_index+1
      else:
         self.match_index = self.match_pointer
         self.match_pointer += 1
         return self.pattern_pointer

   def exhaust_pattern_state(self, tape_index):
      if tape_index >= len(self.tape):
         if not self.match_index >= self.match_limit:
            raise StateError('pattern exhausted with fringe data left on match')
         else:
            raise StateTerminate

      pc = self.tape[tape_index]

      if pc == '*':
         return tape_index+1
      else:
         raise StateError('pattern entered exhaustive state with more than a glob')

   def match(self, value=None):
      self.current_state = self.init_state

      if value:
         self.match_against = value

      try:
         self.run()
         return 1
      except StateError,e:
         #print "StateError: %s" % e
         return 0

class SSHConfigMachine(StateMachine):
   ALL_WHITESPACE = set(' \t\r\n')
   LINE_WHITESPACE = set(' \t,')
   ENTRY_WHITESPACE = set('\r\n')

   def __init__(self, filename, target_host=None):
      fp = open(filename, 'r')
      data = fp.read()
      fp.close()

      self.target_host = target_host
      StateMachine.__init__(self, data, self.init_state)

   def run(self):
      try:
         StateMachine.run(self)
      except IndexError:
         pass

   def init_state(self, tape_index):
      self.current_hosts = ["*"]
      self.current_keyword = None
      self.current_argument = None
      self.current_arguments = None
      self.current_line = 1

      self.config = dict()
      self.current_state = self.read_state
      return tape_index

   def read_state(self, tape_index):
      c = self.tape[tape_index]

      if c == '\n':
         self.current_line += 1

      if c in self.ALL_WHITESPACE:
         return tape_index+1
      elif c == '#':
         self.current_state = self.comment
      else:
         self.current_keyword = list()
         self.current_state = self.keyword

      return tape_index

   def comment(self, tape_index):
      c = self.tape[tape_index]

      if not c in self.ENTRY_WHITESPACE:
         return tape_index+1
      else:
         self.current_state = self.entry_whitespace

      return tape_index

   def keyword(self, tape_index):
      c = self.tape[tape_index]

      if c in self.ENTRY_WHITESPACE:
         raise StateError("unexpected end-of-line attempting to parse keyword for %s. (line %d)" % (', '.join(self.current_hosts), self.current_line))
      elif c in self.LINE_WHITESPACE:
         if self.current_keyword is None:
            raise StateError("found argument whitespace but have no keyword for %s. (line %d)" % (', '.join(self.current_hosts), self.current_line))

         self.current_keyword = ''.join(self.current_keyword)
         self.current_state = self.line_whitespace
         return tape_index

      if self.current_keyword is None:
         self.current_keyword = list()
      else:
         self.current_keyword.append(c)

      return tape_index+1

   def entry_whitespace(self, tape_index):
      c = self.tape[tape_index]

      if not self.current_keyword is None and self.current_argument is None and self.current_arguments is None:
         raise StateError("unexpected end-of-line parsing %s for %s. (line %d)" % (self.current_keyword, ', '.join(self.current_hosts), self.current_line))
      if c in self.ALL_WHITESPACE and self.current_keyword is None:
         self.current_state = self.read_state
         return tape_index

      if self.current_argument:
         self.current_argument = ''.join(self.current_argument)

         if self.current_arguments is None:
            self.current_arguments = [self.current_argument]
         else:
            self.current_arguments.append(self.current_argument)

      self.store_keyword()
      self.current_state = self.read_state

      self.current_keyword = None
      self.current_argument = None
      self.current_arguments = None
      self.current_line += 1

      return tape_index+1

   def line_whitespace(self, tape_index):
      c = self.tape[tape_index]

      if c in self.LINE_WHITESPACE:
         return tape_index+1
      elif c == '#':
         self.current_state = self.comment
      elif c in self.ENTRY_WHITESPACE:
         self.current_state = self.entry_whitespace
      else:
         self.current_state = self.argument

      return tape_index

   def store_keyword(self):
      if self.current_keyword == 'Host':
         self.current_hosts = self.current_arguments[:]
         return

      for host in self.current_hosts:
         if self.target_host:
            if not SSHPatternMachine(host, self.target_host).match():
               continue

            host = self.target_host

         host_store = self.config.setdefault(host, dict())

         if not host_store.has_key(self.current_keyword):
            host_store[self.current_keyword] = self.current_arguments
         else:
            for argument in self.current_arguments:
               host_store[self.current_keyword].append(argument)

   def argument(self, tape_index):
      c = self.tape[tape_index]

      if c in self.ENTRY_WHITESPACE:
         self.current_state = self.entry_whitespace
      elif c in self.LINE_WHITESPACE:
         if not self.current_argument is None:
            self.current_argument = ''.join(self.current_argument)

            if self.current_arguments is None:
               self.current_arguments = list()

            self.current_arguments.append(self.current_argument)
            self.current_argument = None

         self.current_state = self.line_whitespace
      elif c == '"':
         self.quote_count = 0
         self.current_state = self.enclosed_argument
      else:
         if self.current_argument is None:
            self.current_argument = list()

         self.current_argument.append(c)
         return tape_index+1

      return tape_index

   def enclosed_argument(self, tape_index):
      c = self.tape[tape_index]

      if c == '"':
         if not self.quote_count:
            self.quote_count += 1
         else:
            self.current_state = self.read_state

         return tape_index+1
      elif c == '\\':
         self.current_state = self.escape_state
         return tape_index

if __name__ == '__main__':
   if not len(sys.argv):
      sys.stderr.write('no hosts given')
      sys.exit(1)

   for host_query in sys.argv[1:]:
      ssh_machine = SSHConfigMachine("%s/.ssh/config" % os.environ['HOME'], host_query)
      ssh_machine.run()

      hosts = ssh_machine.config.keys()
      hosts.sort()

      for host in hosts:
         print 'Host %s' % host

         properties = ssh_machine.config[host].keys()
         properties.sort()

         for prop in properties:
            print '\t%s %s' % (prop, ','.join(ssh_machine.config[host][prop]))
